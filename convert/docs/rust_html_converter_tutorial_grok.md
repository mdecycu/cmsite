以下內容以你提供的程式為核心，**依功能分段**建立完整的 Rust 程式教材。每個主題都先說明語法與設計意圖，再從原程式擷取對應片段作為主範例，最後再延伸三個實用例子，方便教學與自學。

---

# Rust 程式教材  
以「CMS 靜態 HTML 轉換工具」為實例

---

## 一、struct、derive、Vec、HashMap 等語法與資料結構

### 1.1 核心說明

- **`struct`**：用來定義自訂資料型別，把相關欄位打包在一起。
- **`#[derive(...)]`**：屬性巨集，自動實作常用 Trait（如 `Debug`、`Clone`、`Serialize`）。
- **`Vec<T>`**：動態陣列，可隨時新增元素，是 Rust 最常用的集合。
- **`HashMap<K, V>`**：雜湊表（鍵值對），適合用來計數或快速查找。

### 1.2 原程式主範例

```rust
#[derive(Debug, Clone)]
struct Page {
    title: String,
    filename: String,
    level: usize,
    body: String,
}

#[derive(Debug)]
struct NavNode {
    page_index: usize,
    children: Vec<NavNode>,
}

#[derive(Serialize)]
struct SearchPage {
    title: String,
    text: String,
    tags: String,
    url: String,
}
```

**說明**：
- `Page` 代表一個分頁，使用 `Clone` 方便複製。
- `NavNode` 用 `Vec<NavNode>` 形成樹狀結構。
- `SearchPage` 加上 `Serialize` 後可直接轉成 JSON。

### 1.3 三個延伸實用例子

**例子 1：商品資料結構**
```rust
#[derive(Debug, Clone)]
struct Product {
    id: u32,
    name: String,
    price: f64,
    tags: Vec<String>,
}
```

**例子 2：使用 HashMap 做字頻統計**
```rust
use std::collections::HashMap;

fn word_count(text: &str) -> HashMap<String, usize> {
    let mut map = HashMap::new();
    for word in text.split_whitespace() {
        *map.entry(word.to_string()).or_insert(0) += 1;
    }
    map
}
```

**例子 3：巢狀結構（樹狀目錄）**
```rust
#[derive(Debug)]
struct Folder {
    name: String,
    files: Vec<String>,
    subfolders: Vec<Folder>,
}
```

---

## 二、函式參數、回傳型別、借用、參考、生命週期及 Result、? 錯誤處理

### 2.1 核心說明

| 概念 | 說明 |
|------|------|
| `&T` / `&mut T` | 不可變／可變借用，不取得所有權 |
| `Result<T, E>` | 成功回傳 `Ok(T)`，失敗回傳 `Err(E)` |
| `?` 運算子 | 遇到 `Err` 就提早回傳，成功則取出值 |
| 生命週期 | 編譯器用來確保參考不會比資料活得更久 |

### 2.2 原程式主範例

```rust
fn strip_tags(input: &str) -> Result<String, Box<dyn Error>> {
    let re = Regex::new(r"(?s)<[^>]*>")?;
    let text = re.replace_all(input, "");
    Ok(text
        .replace("&nbsp;", " ")
        .replace("&amp;", "&")
        // ...
    )
}

fn generate(
    input_path: &Path,
    output_dir: &Path,
) -> Result<(), Box<dyn Error>> {
    let input = fs::read_to_string(input_path)?;
    let pages = parse_pages(&input)?;
    // ...
    Ok(())
}
```

**說明**：
- 參數使用 `&str`、`&Path`，只借用不擁有。
- 回傳 `Result`，讓呼叫端決定如何處理錯誤。
- `?` 讓錯誤處理程式碼非常簡潔。

### 2.3 三個延伸實用例子

**例子 1：讀取設定檔**
```rust
fn load_config(path: &str) -> Result<String, Box<dyn Error>> {
    let content = fs::read_to_string(path)?;
    Ok(content)
}
```

**例子 2：安全除法**
```rust
fn safe_divide(a: f64, b: f64) -> Result<f64, String> {
    if b == 0.0 {
        Err("除數不能為零".to_string())
    } else {
        Ok(a / b)
    }
}
```

**例子 3：借用與修改**
```rust
fn append_exclamation(s: &mut String) {
    s.push('!');
}

fn main() {
    let mut text = String::from("Hello");
    append_exclamation(&mut text);
    println!("{}", text); // Hello!
}
```

---

## 三、正規表示式、閉包、迭代器、字串處理與檔名衝突處理

### 3.1 核心說明

- **Regex**：用來匹配與擷取文字。
- **閉包**：可捕捉環境的匿名函式，常搭配迭代器使用。
- **迭代器**：惰性處理序列，搭配 `map`、`filter`、`collect` 非常強大。
- **字串處理**：`replace`、`trim`、`chars`、`collect` 是日常最常用的操作。

### 3.2 原程式主範例

```rust
fn slug_filename(title: &str) -> String {
    let invalid = ['<', '>', ':', '"', '/', '\\', '|', '?', '*'];
    let result: String = title
        .trim()
        .chars()
        .map(|c| {
            if invalid.contains(&c) || c.is_control() {
                '_'
            } else {
                c
            }
        })
        .collect();
    // ...
}

// 檔名衝突處理
let filename_count = filename_counts.entry(key).or_insert(0);
*filename_count += 1;
let filename = if *filename_count == 1 {
    format!("{}.html", base_name)
} else {
    format!("{}-{}.html", base_name, filename_count)
};
```

**說明**：
- 使用 `chars().map().collect()` 把不合法字元替換成 `_`。
- 使用 `HashMap` 計數，解決檔名重複問題。

### 3.3 三個延伸實用例子

**例子 1：簡單的電子郵件驗證**
```rust
fn is_valid_email(email: &str) -> bool {
    let re = Regex::new(r"^[\w\.-]+@[\w\.-]+\.\w+$").unwrap();
    re.is_match(email)
}
```

**例子 2：過濾並轉換數字**
```rust
let numbers: Vec<i32> = vec![1, 2, 3, 4, 5, 6];
let even_squares: Vec<i32> = numbers
    .iter()
    .filter(|&&n| n % 2 == 0)
    .map(|n| n * n)
    .collect();
```

**例子 3：產生不重複的檔名**
```rust
fn unique_filename(base: &str, existing: &mut HashMap<String, usize>) -> String {
    let key = base.to_lowercase();
    let count = existing.entry(key).or_insert(0);
    *count += 1;
    if *count == 1 {
        format!("{}.txt", base)
    } else {
        format!("{}-{}.txt", base, count)
    }
}
```

---

## 四、HTML 樣板、CSS 排版、樹狀導覽、Previous／Next 分頁連結

### 4.1 核心說明

- 使用 **raw string**（`r##"..."##`）方便嵌入大量 HTML／CSS／JS。
- 在 `format!` 中若要輸出大括號，必須寫成 `{{` 與 `}}`。
- 樹狀導覽使用遞迴建立與渲染。
- Previous／Next 使用同一函式，上下各呼叫一次，保持版面一致。

### 4.2 原程式主範例

```rust
fn html_header(title: &str) -> String {
    format!(
        r##"<!DOCTYPE html>
...
.title {{ color: blue; }}
...
"##,
        title = escape_html(title)
    )
}

fn render_previous_next(index: usize, pages: &[Page]) -> String {
    // 產生 Previous 與 Next 連結
}
```

**說明**：
- 導覽選單透過 `build_navigation_tree` + `render_nav_nodes` 遞迴產生。
- Previous／Next 使用 flex 排版，左邊 Previous、右邊 Next。

### 4.3 三個延伸實用例子

**例子 1：簡單的 HTML 樣板函式**
```rust
fn simple_page(title: &str, content: &str) -> String {
    format!(
        r#"<!DOCTYPE html>
<html>
<head><title>{}</title></head>
<body><h1>{}</h1><div>{}</div></body>
</html>"#,
        title, title, content
    )
}
```

**例子 2：遞迴產生目錄樹 HTML**
```rust
fn render_folder(folder: &Folder) -> String {
    let mut html = format!("<li>{}<ul>", folder.name);
    for sub in &folder.subfolders {
        html.push_str(&render_folder(sub));
    }
    html.push_str("</ul></li>");
    html
}
```

**例子 3：分頁導覽列**
```rust
fn pagination(current: usize, total: usize) -> String {
    let mut html = String::from("<div class='pagination'>");
    if current > 1 {
        html.push_str(&format!("<a href='?page={}'>上一頁</a>", current - 1));
    }
    if current < total {
        html.push_str(&format!("<a href='?page={}'>下一頁</a>", current + 1));
    }
    html.push_str("</div>");
    html
}
```

---

## 五、檔案讀寫、JSON 序列化、命令列參數及程式進入點 main()

### 5.1 核心說明

- `fs::read_to_string` / `fs::write`：最常用的檔案讀寫方式。
- `serde_json::to_string`：把實作了 `Serialize` 的資料轉成 JSON 字串。
- `env::args()`：取得命令列參數。
- `main()`：程式進入點，通常負責解析參數並呼叫核心邏輯。

### 5.2 原程式主範例

```rust
fn generate(input_path: &Path, output_dir: &Path) -> Result<(), Box<dyn Error>> {
    let input = fs::read_to_string(input_path)?;
    // ...
    let search_json = serde_json::to_string(&search_pages)?;
    fs::write(output_dir.join("tipuesearch_content.js"), search_js)?;
    Ok(())
}

fn main() {
    let args: Vec<String> = env::args().collect();
    // 解析參數並呼叫 generate
}
```

**說明**：
- 使用 `?` 讓檔案操作失敗時能優雅地往上傳遞錯誤。
- `main` 只負責參數解析與錯誤顯示，真正邏輯放在 `generate`。

### 5.3 三個延伸實用例子

**例子 1：讀取並寫入檔案**
```rust
fn copy_file(src: &str, dst: &str) -> Result<(), Box<dyn Error>> {
    let content = fs::read_to_string(src)?;
    fs::write(dst, content)?;
    Ok(())
}
```

**例子 2：把資料輸出成 JSON 檔**
```rust
#[derive(Serialize)]
struct User { name: String, age: u32 }

fn save_users(users: &[User], path: &str) -> Result<(), Box<dyn Error>> {
    let json = serde_json::to_string_pretty(users)?;
    fs::write(path, json)?;
    Ok(())
}
```

**例子 3：完整的命令列小工具**
```rust
fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("用法：{} <檔案>", args[0]);
        std::process::exit(1);
    }
    match fs::read_to_string(&args[1]) {
        Ok(content) => println!("檔案內容：\n{}", content),
        Err(e) => {
            eprintln!("讀取失敗：{}", e);
            std::process::exit(1);
        }
    }
}
```

---

## 教材使用建議

1. **先講資料結構** → 讓學生了解 `Page`、`NavNode` 的設計。
2. **再講函式與錯誤處理** → 強調借用與 `Result` 的重要性。
3. **接著講文字處理** → 正規表示式與迭代器是重點。
4. **然後講 HTML 產生** → 把前面學到的字串與遞迴應用出來。
5. **最後講檔案與主程式** → 把整支程式串起來。

這份教材可直接用於課堂講解、作業範例或自學講義。若需要，我可以再幫你把每個段落改成「講解稿 + 投影片重點」格式。