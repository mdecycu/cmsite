import js, asyncio

CELL_SIZE = 40
WALL_THICKNESS = 6
#IMG_PATH = "./../images/reeborg/images/"
hostname = js.window.location.hostname

if hostname in ("localhost", "127.0.0.1"):
    IMG_PATH = "./../images/reeborg/images/"
else:
    IMG_PATH = "./images/reeborg/images/"

print(hostname, IMG_PATH)

class World:
    _image_cache = {}

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.layers = self._create_layers()
        self._init_html()

    def _create_layers(self):
        return {
            "grid": js.document.createElement("canvas"),
            "walls": js.document.createElement("canvas"),
            "objects": js.document.createElement("canvas"),
            "robots": js.document.createElement("canvas"),
        }

    def _init_html(self):
        container = js.document.createElement("div")
        container.style.position = "relative"
        container.style.width = f"{self.width * CELL_SIZE}px"
        container.style.height = f"{self.height * CELL_SIZE}px"

        for z, canvas in enumerate(self.layers.values()):
            canvas.width = self.width * CELL_SIZE
            canvas.height = self.height * CELL_SIZE
            canvas.style.position = "absolute"
            canvas.style.top = "0px"
            canvas.style.left = "0px"
            canvas.style.zIndex = str(z)
            container.appendChild(canvas)

        js.document.getElementById("brython_div1").innerHTML = ""
        js.document.getElementById("brython_div1").appendChild(container)

    def _draw_grid(self):
        ctx = self.layers["grid"].getContext("2d")
        ctx.strokeStyle = "#cccccc"
        for i in range(self.width + 1):
            ctx.beginPath()
            ctx.moveTo(i * CELL_SIZE, 0)
            ctx.lineTo(i * CELL_SIZE, self.height * CELL_SIZE)
            ctx.stroke()
        for j in range(self.height + 1):
            ctx.beginPath()
            ctx.moveTo(0, j * CELL_SIZE)
            ctx.lineTo(self.width * CELL_SIZE, j * CELL_SIZE)
            ctx.stroke()

    def _draw_image(self, ctx, img_key, x, y, w, h, offset_x=0, offset_y=0):
        img = World._image_cache.get(img_key)
        if img and img.complete and img.naturalWidth > 0:
            px = x * CELL_SIZE + offset_x
            py = (self.height - 1 - y) * CELL_SIZE + offset_y
            ctx.drawImage(img, px, py, w, h)
            return True
        else:
            print(f"⚠️ Image '{img_key}' not ready for drawing.")
            return False

    async def _draw_walls(self):
        ctx = self.layers["walls"].getContext("2d")
        ctx.clearRect(0, 0, self.width * CELL_SIZE, self.height * CELL_SIZE)
        success = True
        for x in range(self.width):
            success &= self._draw_image(ctx, "north", x, self.height - 1, CELL_SIZE, WALL_THICKNESS, offset_y=0)
            success &= self._draw_image(ctx, "north", x, 0, CELL_SIZE, WALL_THICKNESS, offset_y=CELL_SIZE - WALL_THICKNESS)
        for y in range(self.height):
            success &= self._draw_image(ctx, "east", 0, y, WALL_THICKNESS, CELL_SIZE, offset_x=0)
            success &= self._draw_image(ctx, "east", self.width - 1, y, WALL_THICKNESS, CELL_SIZE, offset_x=CELL_SIZE - WALL_THICKNESS)
        return success

    async def _preload_images(self):
        image_files = {
            "blue_robot_e": "blue_robot_e.png",
            "blue_robot_n": "blue_robot_n.png",
            "blue_robot_w": "blue_robot_w.png",
            "blue_robot_s": "blue_robot_s.png",
            "north": "north.png",
            "east": "east.png",
        }

        promises = []
        for key, filename in image_files.items():
            if key in World._image_cache and World._image_cache[key].complete:
                continue
            
            img = js.document.createElement("img")
            img.crossOrigin = "Anonymous"
            img.src = IMG_PATH + filename
            World._image_cache[key] = img

            def make_promise(img_element):
                def executor(resolve, reject):
                    def on_load(event):
                        img_element.removeEventListener("load", on_load)
                        img_element.removeEventListener("error", on_error)
                        resolve(img_element)
                    def on_error(event):
                        img_element.removeEventListener("load", on_load)
                        img_element.removeEventListener("error", on_error)
                        reject(js.Error.new(f"Failed to load image: {img_element.src}"))
                    img_element.addEventListener("load", on_load)
                    img_element.addEventListener("error", on_error)
                    if img_element.complete and img_element.naturalWidth > 0:
                        resolve(img_element)
                return js.Promise.new(executor)
            promises.append(make_promise(img))

        if not promises:
            print("✅ Images already cached.")
            return True

        try:
            await js.await_promise(js.Promise.all(promises))
            print("✅ Image preloading promises resolved.")
            return True
        except Exception as e:
            print(f"🚨 Error during image preloading: {e}")
            return False

    async def setup(self):
        """非同步設定世界，確保所有資源都就緒。"""
        await self._preload_images()
        
        # Yield to event loop to ensure DOM updates
        print("▶️ Yielding to event loop for one tick...")
        await asyncio.sleep(0)
        print("◀️ Resuming execution.")

        self._draw_grid()
        
        # Retry drawing walls up to 3 times if images are not ready
        for attempt in range(3):
            if await self._draw_walls():
                break
            print(f"⚠️ Walls not drawn, retrying ({attempt + 1}/3)...")
            await asyncio.sleep(0.1)
        else:
            print("🚨 Failed to draw walls after retries.")

        # Check robot image readiness
        robot_img_key = "blue_robot_e"
        if not (World._image_cache.get(robot_img_key) and World._image_cache[robot_img_key].complete):
            print(f"🚨 Robot image '{robot_img_key}' still not ready after setup!")

class AnimatedRobot:
    def __init__(self, world, x, y):
        self.world = world
        self.x = x - 1
        self.y = y - 1
        self.facing = "E"
        self.facing_order = ["E", "N", "W", "S"]
        self.robot_ctx = world.layers["robots"].getContext("2d")
        self.trace_ctx = world.layers["objects"].getContext("2d")
        self._draw_robot()

    def _robot_image_key(self):
        return f"blue_robot_{self.facing.lower()}"

    def _draw_robot(self):
        self.robot_ctx.clearRect(0, 0, self.world.width * CELL_SIZE, self.world.height * CELL_SIZE)
        self.world._draw_image(self.robot_ctx, self._robot_image_key(), self.x, self.y, CELL_SIZE, CELL_SIZE)

    def _draw_trace(self, from_x, from_y, to_x, to_y):
        ctx = self.trace_ctx
        ctx.strokeStyle = "#d33"
        ctx.lineWidth = 2
        ctx.beginPath()
        fx = from_x * CELL_SIZE + CELL_SIZE / 2
        fy = (self.world.height - 1 - from_y) * CELL_SIZE + CELL_SIZE / 2
        tx = to_x * CELL_SIZE + CELL_SIZE / 2
        ty = (self.world.height - 1 - to_y) * CELL_SIZE + CELL_SIZE / 2
        ctx.moveTo(fx, fy)
        ctx.lineTo(tx, ty)
        ctx.stroke()

    async def move(self, steps):
        for _ in range(steps):
            from_x, from_y = self.x, self.y
            dx, dy = 0, 0
            if self.facing == "E": dx = 1
            elif self.facing == "W": dx = -1
            elif self.facing == "N": dy = 1
            elif self.facing == "S": dy = -1
            next_x = self.x + dx
            next_y = self.y + dy
            if 0 <= next_x < self.world.width and 0 <= next_y < self.world.height:
                self.x, self.y = next_x, next_y
                self._draw_trace(from_x, from_y, self.x, self.y)
                self._draw_robot()
                await asyncio.sleep(0.2)
            else:
                print("🚨 已經撞牆，停止移動！")
                break

    async def turn_left(self):
        idx = self.facing_order.index(self.facing)
        self.facing = self.facing_order[(idx + 1) % 4]
        self._draw_robot()
        await asyncio.sleep(0.3)

async def start_robot_patrol():
    print("🚀 Starting robot patrol simulation...")
    world = World(10, 10)
    await world.setup()

    print("🤖 Creating robot instance.")
    robot_instance = AnimatedRobot(world, 1, 1)
    
    print("🧭 Robot patrol sequence started.")
    await robot_instance.move(9)
    await robot_instance.turn_left()
    await robot_instance.move(9)
    await robot_instance.turn_left()
    await robot_instance.move(9)
    await robot_instance.turn_left()
    await robot_instance.move(9)
    
    print("🚩 巡邏完成！")

asyncio.create_task(start_robot_patrol())