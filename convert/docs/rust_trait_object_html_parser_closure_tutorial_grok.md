# Rust 進階核心概念教材  
## Trait Object · HTML Parser · 閉包

---

## 一、Trait Object（特徵物件）

### 1.1 什麼是 Trait Object？

在 Rust 中，**Trait Object** 是一種「動態分派」（Dynamic Dispatch）的機制。  
當我們不確定具體型別、只知道該型別實作了某個 Trait 時，就可以使用 `dyn Trait` 來表示。

常見寫法：
```rust
Box<dyn Trait>
&dyn Trait
Arc<dyn Trait>
```

Trait Object 的核心特點：
- 使用 **虛表（vtable）** 進行方法查找
- 犧牲一點效能換取極大的彈性
- 常用於「插件系統」、「策略模式」、「異質集合」等場景

### 1.2 與泛型的比較

| 比較項目       | 泛型（靜態分派）     | Trait Object（動態分派）     |
|----------------|----------------------|------------------------------|
| 效能           | 較高（編譯期展開）   | 稍低（運行時查表）           |
| 程式碼大小     | 可能膨脹             | 較精簡                       |
| 型別資訊       | 編譯期確定           | 運行時才知道                 |
| 適用場景       | 效能敏感、型別固定   | 需要彈性、異質集合           |

---

### 1.3 五個實用範例

#### 範例 1：異質集合（最常見的用法）

```rust
trait Animal {
    fn speak(&self);
}

struct Dog;
struct Cat;
struct Bird;

impl Animal for Dog {
    fn speak(&self) { println!("汪汪！"); }
}

impl Animal for Cat {
    fn speak(&self) { println!("喵～"); }
}

impl Animal for Bird {
    fn speak(&self) { println!("啾啾！"); }
}

fn main() {
    let animals: Vec<Box<dyn Animal>> = vec![
        Box::new(Dog),
        Box::new(Cat),
        Box::new(Bird),
    ];

    for animal in animals {
        animal.speak();
    }
}
```

**說明**：  
`Vec<Box<dyn Animal>>` 可以同時存放不同型別的動物，這是泛型做不到的（除非使用 enum）。

---

#### 範例 2：策略模式（可替換的演算法）

```rust
trait SortStrategy {
    fn sort(&self, data: &mut [i32]);
}

struct BubbleSort;
struct QuickSort;

impl SortStrategy for BubbleSort {
    fn sort(&self, data: &mut [i32]) {
        // 簡單氣泡排序實作
        let n = data.len();
        for i in 0..n {
            for j in 0..n - i - 1 {
                if data[j] > data[j + 1] {
                    data.swap(j, j + 1);
                }
            }
        }
    }
}

impl SortStrategy for QuickSort {
    fn sort(&self, data: &mut [i32]) {
        data.sort(); // 簡化示範
    }
}

fn perform_sort(strategy: &dyn SortStrategy, data: &mut [i32]) {
    strategy.sort(data);
}

fn main() {
    let mut numbers = vec![5, 2, 9, 1, 7];
    perform_sort(&BubbleSort, &mut numbers);
    println!("{:?}", numbers);
}
```

**說明**：  
可以在執行時動態切換排序策略，非常適合需要熱替換演算法的場景。

---

#### 範例 3：回調系統 / 事件處理

```rust
trait EventHandler {
    fn handle(&self, event: &str);
}

struct Logger;
struct Notifier;

impl EventHandler for Logger {
    fn handle(&self, event: &str) {
        println!("[LOG] {}", event);
    }
}

impl EventHandler for Notifier {
    fn handle(&self, event: &str) {
        println!("[NOTIFY] 發送通知：{}", event);
    }
}

struct EventSystem {
    handlers: Vec<Box<dyn EventHandler>>,
}

impl EventSystem {
    fn new() -> Self {
        Self { handlers: Vec::new() }
    }

    fn register(&mut self, handler: Box<dyn EventHandler>) {
        self.handlers.push(handler);
    }

    fn emit(&self, event: &str) {
        for handler in &self.handlers {
            handler.handle(event);
        }
    }
}

fn main() {
    let mut system = EventSystem::new();
    system.register(Box::new(Logger));
    system.register(Box::new(Notifier));
    system.emit("使用者登入");
}
```

**說明**：  
這是典型的觀察者模式實作，Trait Object 讓事件系統可以接受任意實作了 `EventHandler` 的型別。

---

#### 範例 4：插件系統

```rust
trait Plugin {
    fn name(&self) -> &str;
    fn execute(&self);
}

struct ImagePlugin;
struct AudioPlugin;

impl Plugin for ImagePlugin {
    fn name(&self) -> &str { "Image Processor" }
    fn execute(&self) { println!("處理圖片中..."); }
}

impl Plugin for AudioPlugin {
    fn name(&self) -> &str { "Audio Processor" }
    fn execute(&self) { println!("處理音訊中..."); }
}

fn load_plugins() -> Vec<Box<dyn Plugin>> {
    vec![
        Box::new(ImagePlugin),
        Box::new(AudioPlugin),
    ]
}

fn main() {
    let plugins = load_plugins();
    for plugin in plugins {
        println!("載入插件：{}", plugin.name());
        plugin.execute();
    }
}
```

**說明**：  
非常適合做可擴充的應用程式架構，未來新增插件只需實作 Trait 即可，不需修改主程式。

---

#### 範例 5：錯誤處理的統一介面

```rust
use std::error::Error;
use std::fmt;

#[derive(Debug)]
struct AppError {
    message: String,
}

impl fmt::Display for AppError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.message)
    }
}

impl Error for AppError {}

fn might_fail(success: bool) -> Result<(), Box<dyn Error>> {
    if success {
        Ok(())
    } else {
        Err(Box::new(AppError {
            message: "發生錯誤".to_string(),
        }))
    }
}

fn main() {
    match might_fail(false) {
        Ok(_) => println!("成功"),
        Err(e) => println!("錯誤：{}", e),
    }
}
```

**說明**：  
`Box<dyn Error>` 是 Rust 中最常見的錯誤處理方式之一，讓不同來源的錯誤可以統一回傳。

---

## 二、HTML Parser（HTML 解析）

### 2.1 Rust 中常見的 HTML 解析庫

| 庫名稱       | 特點                              | 適用場景                     |
|--------------|-----------------------------------|------------------------------|
| `scraper`    | 基於 CSS 選擇器，易用             | 網頁爬蟲、資料抽取           |
| `html5ever`  | 完整 HTML5 解析器（Servo 專案）   | 需要精確解析的場景           |
| `select`     | 輕量級選擇器                      | 簡單抽取                     |
| `tl`         | 高效能、低記憶體                  | 大量網頁處理                 |

本教材以目前最流行的 **`scraper`** 為主。

### 2.2 安裝

```toml
[dependencies]
scraper = "0.20"
reqwest = { version = "0.12", features = ["blocking"] }  # 若需要下載網頁
```

---

### 2.3 五個實用範例

#### 範例 1：基本解析與選擇器

```rust
use scraper::{Html, Selector};

fn main() {
    let html = r#"
        <html>
            <body>
                <div class="product">
                    <h2>Rust 程式設計</h2>
                    <span class="price">NT$ 680</span>
                </div>
            </body>
        </html>
    "#;

    let document = Html::parse_document(html);
    let title_selector = Selector::parse("h2").unwrap();
    let price_selector = Selector::parse(".price").unwrap();

    let title = document.select(&title_selector).next().unwrap().text().collect::<String>();
    let price = document.select(&price_selector).next().unwrap().text().collect::<String>();

    println!("書名：{}", title);
    println!("價格：{}", price);
}
```

**說明**：  
最基本的用法。`Selector::parse` 支援完整 CSS 選擇器語法。

---

#### 範例 2：批次抽取多筆資料

```rust
use scraper::{Html, Selector};

fn main() {
    let html = r#"
        <ul class="books">
            <li><a href="/book/1">Rust 入門</a></li>
            <li><a href="/book/2">進階 Rust</a></li>
            <li><a href="/book/3">Rust 併發程式設計</a></li>
        </ul>
    "#;

    let document = Html::parse_document(html);
    let selector = Selector::parse("ul.books li a").unwrap();

    for element in document.select(&selector) {
        let title = element.text().collect::<String>();
        let href = element.value().attr("href").unwrap_or("#");
        println!("{} -> {}", title, href);
    }
}
```

**說明**：  
適合用來爬取商品列表、文章列表等重複結構。

---

#### 範例 3：處理表格資料

```rust
use scraper::{Html, Selector};

fn main() {
    let html = r#"
        <table>
            <tr><th>姓名</th><th>分數</th></tr>
            <tr><td>小明</td><td>92</td></tr>
            <tr><td>小華</td><td>88</td></tr>
            <tr><td>小美</td><td>95</td></tr>
        </table>
    "#;

    let document = Html::parse_document(html);
    let row_selector = Selector::parse("tr").unwrap();
    let cell_selector = Selector::parse("td").unwrap();

    for row in document.select(&row_selector).skip(1) { // 跳過表頭
        let cells: Vec<String> = row.select(&cell_selector)
            .map(|c| c.text().collect::<String>())
            .collect();
        if cells.len() == 2 {
            println!("{} 的分數是 {}", cells[0], cells[1]);
        }
    }
}
```

**說明**：  
表格是網頁中常見的結構化資料來源，這個模式非常實用。

---

#### 範例 4：結合 reqwest 爬取真實網頁

```rust
use reqwest::blocking::get;
use scraper::{Html, Selector};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let response = get("https://www.rust-lang.org/")?.text()?;
    let document = Html::parse_document(&response);

    let selector = Selector::parse("h1, h2").unwrap();

    println!("網頁標題與大標：");
    for element in document.select(&selector) {
        let text = element.text().collect::<String>().trim().to_string();
        if !text.is_empty() {
            println!("- {}", text);
        }
    }
    Ok(())
}
```

**說明**：  
實際專案中最常用的模式：下載網頁 → 解析 → 抽取資料。

---

#### 範例 5：移除標籤、只保留純文字

```rust
use scraper::{Html, Selector};

fn extract_text(html: &str) -> String {
    let document = Html::parse_document(html);
    let selector = Selector::parse("body").unwrap();

    document
        .select(&selector)
        .next()
        .map(|body| body.text().collect::<Vec<_>>().join(" "))
        .unwrap_or_default()
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}

fn main() {
    let html = r#"
        <html>
            <body>
                <h1>歡迎</h1>
                <p>這是一段 <strong>重要</strong> 的文字。</p>
                <script>alert('不要被抓到');</script>
            </body>
        </html>
    "#;

    println!("{}", extract_text(html));
}
```

**說明**：  
很多時候我們只需要純文字內容（例如做全文搜尋或摘要），這個函式非常實用。

---

## 三、閉包（Closures）

### 3.1 什麼是閉包？

閉包是可以「捕捉」周圍環境變數的匿名函式。  
Rust 的閉包非常強大，且與所有權系統緊密整合。

三種 Trait：
- `Fn`：不可變借用
- `FnMut`：可變借用
- `FnOnce`：取得所有權（只能呼叫一次）

### 3.2 閉包語法

```rust
|參數| 表達式
|參數| { 多行程式碼 }
```

---

### 3.3 五個實用範例

#### 範例 1：基本捕捉與使用

```rust
fn main() {
    let name = String::from("小明");
    let age = 25;

    let greet = || {
        println!("你好，我是 {}，今年 {} 歲", name, age);
    };

    greet();
    // name 和 age 仍然可以使用，因為閉包只是借用
    println!("名字還在：{}", name);
}
```

**說明**：  
最基本的閉包用法，預設使用不可變借用（`Fn`）。

---

#### 範例 2：作為函式參數（高階函式）

```rust
fn apply_operation(x: i32, y: i32, op: impl Fn(i32, i32) -> i32) -> i32 {
    op(x, y)
}

fn main() {
    let add = |a, b| a + b;
    let multiply = |a, b| a * b;

    println!("5 + 3 = {}", apply_operation(5, 3, add));
    println!("5 * 3 = {}", apply_operation(5, 3, multiply));

    // 也可以直接傳入匿名閉包
    println!("5 - 3 = {}", apply_operation(5, 3, |a, b| a - b));
}
```

**說明**：  
這是函數式程式設計的核心概念，讓程式碼更加靈活。

---

#### 範例 3：迭代器搭配閉包（最常見）

```rust
fn main() {
    let numbers = vec![1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

    // 過濾偶數 → 平方 → 加總
    let result: i32 = numbers
        .iter()
        .filter(|&n| n % 2 == 0)
        .map(|n| n * n)
        .sum();

    println!("偶數平方和：{}", result);

    // 找出第一個大於 5 的數字
    let first_big = numbers.iter().find(|&&n| n > 5);
    println!("第一個大於 5 的數字：{:?}", first_big);
}
```

**說明**：  
Rust 的迭代器幾乎都是靠閉包驅動的，這是日常開發中使用頻率最高的場景。

---

#### 範例 4：可變捕捉（FnMut）

```rust
fn main() {
    let mut count = 0;

    let mut increment = || {
        count += 1;
        println!("目前計數：{}", count);
    };

    increment();
    increment();
    increment();

    println!("最終 count = {}", count);
}
```

**說明**：  
當閉包需要修改捕捉的變數時，會自動實作 `FnMut`。

---

#### 範例 5：移動所有權（move 閉包）與執行緒

```rust
use std::thread;

fn main() {
    let data = vec![1, 2, 3, 4, 5];

    let handle = thread::spawn(move || {
        println!("執行緒中的資料：{:?}", data);
        data.iter().sum::<i32>()
    });

    // 這裡不能再使用 data，因為所有權已經被 move 進閉包
    // println!("{:?}", data); // 編譯錯誤

    let sum = handle.join().unwrap();
    println!("總和：{}", sum);
}
```

**說明**：  
`move` 關鍵字強制閉包取得所有權，這在多執行緒、非同步程式中非常重要。

---

## 總結比較表

| 概念            | 核心價值                         | 最常見使用場景                     |
|-----------------|----------------------------------|------------------------------------|
| Trait Object    | 動態分派、異質集合               | 插件系統、策略模式、事件處理       |
| HTML Parser     | 從非結構化資料中抽取資訊         | 爬蟲、資料清洗、網頁內容分析       |
| 閉包            | 簡潔表達行為、捕捉環境           | 迭代器、回調、高階函式、執行緒     |

---

以上內容涵蓋了理論說明、對比表格與五個完整可運行的實用範例，適合直接作為課堂教材、自學講義或技術分享投影片的基礎內容。