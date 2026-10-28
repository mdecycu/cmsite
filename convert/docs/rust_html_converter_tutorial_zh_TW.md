# 以 HTML 轉換器為主線的 Rust 程式教材
## 從 `convert.exe` 範例學習 Rust 語法、資料結構、錯誤處理與網頁輸出

本教材以先前的 `convert_annotated.rs`／HTML 轉換器為主線。程式的主要工作是：

1. 讀取 `config/content.htm`（或命令列指定的輸入檔）。
2. 尋找 `h1`、`h2`、`h3` 標題，將內容切成多個分頁。
3. 為每頁產生安全且不重複的檔名。
4. 建立樹狀導覽、Previous／Next 連結與網站地圖。
5. 寫出 `index.html`、各分頁、`sitemap.html` 與搜尋索引 JavaScript。

預設執行方式是從專案根目錄執行 `convert.exe`，輸入 `config/content.htm`，輸出到 `content/`；也可以指定輸入檔及輸出目錄。

> 閱讀方式：先看「原程式用途」，再理解 Rust 語法，最後試跑三個延伸例子。例子是可移植的小片段，需放在適當函式或 `main()` 中才能編譯；有使用外部 crate 的例子會明確標示。

---

# 第一章：`struct`、`derive`、`Vec`、`HashMap`

## 1.1 `struct`：把相關資料組合成一個型別

原程式的 `Page`：

```rust
#[derive(Debug, Clone)]
struct Page {
    title: String,
    filename: String,
    level: usize,
    body: String,
}
```

`struct`（結構體）讓程式設計者定義自己的資料型別。這裡一個 `Page` 就代表一個輸出的 HTML 分頁：

- `title: String`：頁面標題。
- `filename: String`：輸出檔名。
- `level: usize`：來源標題層級，例如 `h1`、`h2`、`h3` 對應 1、2、3。
- `body: String`：該頁的 HTML 本文。

`String` 是可擁有、可增長的 UTF-8 字串；`usize` 是適合表示索引或集合長度的無號整數型別。結構體欄位預設是私有的；若要讓其他模組存取，通常需要依需求加上 `pub`。

### 例子一：定義網站資源

```rust
#[derive(Debug)]
struct Asset {
    path: String,
    kind: String,
    required: bool,
}

fn main() {
    let asset = Asset {
        path: "cms/static/style.css".to_string(),
        kind: "css".to_string(),
        required: true,
    };

    println!("{asset:?}");
}
```

用途：將路徑、資源種類與是否必要等相關資訊集中管理，而不是用三個互不關聯的變數。

### 例子二：定義轉換設定

```rust
struct ConvertConfig {
    input: String,
    output_dir: String,
    include_sitemap: bool,
}

let config = ConvertConfig {
    input: "config/content.htm".to_string(),
    output_dir: "content".to_string(),
    include_sitemap: true,
};
```

用途：當設定項目增加時，將它們包在同一個設定物件中，函式就能接收一個設定參數，而不是接收很多個零散參數。

### 例子三：定義搜尋結果

```rust
struct SearchHit {
    title: String,
    url: String,
    score: u32,
}

let hit = SearchHit {
    title: "安裝說明".to_string(),
    url: "安裝說明.html".to_string(),
    score: 10,
};
```

用途：搜尋程式可以將標題、連結及排序分數一起傳遞。這和原程式的 `SearchPage` 概念相近，但 `score` 是此延伸例子新增的欄位。

## 1.2 `derive`：自動產生常用 trait 實作

原程式使用：

```rust
#[derive(Debug, Clone)]
struct Page { /* 欄位略 */ }

#[derive(Serialize)]
struct SearchPage { /* 欄位略 */ }
```

`#[derive(...)]` 是屬性語法，要求編譯器或 derive 巨集替型別產生 trait 實作。

- `Debug`：可使用 `{:?}` 或 `{:#?}` 除錯輸出。
- `Clone`：允許明確呼叫 `.clone()` 複製值；它不代表每次賦值都會自動複製。
- `Serialize`：由 `serde` 提供，讓結構體可序列化成 JSON 等格式。

`Serialize` 需要在 `Cargo.toml` 啟用 serde 的 `derive` feature，並在程式中匯入 `serde::Serialize`。

### 例子一：除錯輸出

```rust
#[derive(Debug)]
struct PageInfo {
    title: String,
    level: usize,
}

let info = PageInfo {
    title: "首頁".to_string(),
    level: 1,
};
println!("{info:?}");
println!("{info:#?}"); // 多行、較易閱讀的除錯格式
```

### 例子二：明確複製資料

```rust
#[derive(Clone, Debug)]
struct OutputOptions {
    directory: String,
}

let first = OutputOptions {
    directory: "content".to_string(),
};
let second = first.clone();
println!("{first:?}");
println!("{second:?}");
```

`clone()` 會複製字串內容。複製大型資料可能有成本，應在確實需要獨立擁有資料時使用。

### 例子三：序列化成 JSON（需 `serde` 與 `serde_json`）

```rust
use serde::Serialize;

#[derive(Serialize)]
struct Link {
    title: String,
    url: String,
}

let link = Link {
    title: "首頁".to_string(),
    url: "index.html".to_string(),
};
let json = serde_json::to_string(&link)?;
println!("{json}");
```

這個例子放在回傳 `Result` 的函式中，才能直接使用 `?`。在 `main()` 中也可以改用 `serde_json::to_string(&link).expect("序列化失敗")`，但 `expect` 會在失敗時 panic。

## 1.3 `Vec<T>`：可變長度序列

原程式有：

```rust
let mut pages: Vec<Page> = Vec::new();
pages.push(Page { /* ... */ });
```

`Vec<T>` 是存放相同型別 `T` 的可變長度序列。`Vec::new()` 建立空向量，`push()` 加入元素，`len()` 取得數量，`iter()` 借用遍歷元素。若要修改向量本身，例如 `push()`，變數通常必須宣告為 `mut`。

### 例子一：收集檔名

```rust
let mut filenames: Vec<String> = Vec::new();
filenames.push("index.html".to_string());
filenames.push("sitemap.html".to_string());

for name in &filenames {
    println!("{name}");
}
```

### 例子二：用 `vec!` 快速建立清單

```rust
let levels = vec![1_usize, 2, 3];
println!("共有 {} 個層級", levels.len());
```

`vec![...]` 是常用的向量建立巨集；第一個元素的型別通常會協助推導整個向量的元素型別。

### 例子三：過濾分頁

```rust
let pages = vec![
    ("首頁".to_string(), 1_usize),
    ("安裝".to_string(), 2),
    ("細節".to_string(), 3),
];

let detailed: Vec<_> = pages
    .iter()
    .filter(|(_, level)| *level >= 2)
    .cloned()
    .collect();
```

這裡 `iter()` 借用元素，`filter()` 保留符合條件的元素，`cloned()` 複製元素，`collect()` 收集成新的 `Vec`。`Vec<_>` 的 `_` 表示讓編譯器推導元素型別。

## 1.4 `HashMap<K, V>`：以鍵查找值

原程式使用：

```rust
let mut title_counts: HashMap<String, usize> = HashMap::new();
let count = title_counts.entry(title.clone()).or_insert(0);
*count += 1;
```

`HashMap<K, V>` 是雜湊表，讓程式以鍵 `K` 快速查找對應的值 `V`。這裡用標題當鍵、出現次數當值。

- `entry(key)`：取得該鍵的入口。
- `or_insert(0)`：若鍵不存在，就插入預設值 `0`，並回傳對應值的可變參考。
- `*count += 1`：`count` 是參考，`*` 解參考後修改實際數值。

### 例子一：計算標題出現次數

```rust
use std::collections::HashMap;

let mut counts = HashMap::new();
for title in ["介紹", "安裝", "介紹"] {
    *counts.entry(title).or_insert(0_usize) += 1;
}
assert_eq!(counts.get("介紹"), Some(&2));
```

### 例子二：統計副檔名數量

```rust
use std::collections::HashMap;

let filenames = ["a.html", "b.css", "c.html"];
let mut counts: HashMap<&str, usize> = HashMap::new();

for filename in filenames {
    if let Some((_, extension)) = filename.rsplit_once('.') {
        *counts.entry(extension).or_insert(0) += 1;
    }
}
```

`rsplit_once('.')` 從右側尋找第一個句點，成功時回傳前後兩部分；沒有句點時回傳 `None`。

### 例子三：建立標題到檔名的對照

```rust
use std::collections::HashMap;

let mut routes = HashMap::new();
routes.insert("首頁".to_string(), "index.html".to_string());
routes.insert("網站地圖".to_string(), "sitemap.html".to_string());

if let Some(filename) = routes.get("首頁") {
    println!("首頁檔案：{filename}");
}
```

`get()` 回傳 `Option<&V>`，所以要用 `if let Some(...)`、`match` 或其他方式處理可能不存在的鍵。

---

# 第二章：函式、參數、回傳型別、借用、參考、生命週期與錯誤處理

## 2.1 函式參數與回傳型別

原程式：

```rust
fn slug_filename(title: &str) -> String {
    // ...
}
```

- `fn` 宣告函式。
- `title: &str` 表示函式借用一段字串，不取得字串所有權。
- `-> String` 表示回傳一個擁有所有權的字串。
- 函式最後一個運算式若沒有分號，就是回傳值；也可明確寫 `return value;`。

### 例子一：回傳整理過的標題

```rust
fn normalize_title(title: &str) -> String {
    title.trim().to_lowercase()
}
```

`trim()` 去除首尾空白；`to_lowercase()` 產生小寫字串。這個函式不修改呼叫端的原字串。

### 例子二：接收多個參數

```rust
fn make_link(title: &str, filename: &str) -> String {
    format!("<a href=\"{}\">{}</a>", filename, title)
}
```

這是簡化示範。若 `title` 或 `filename` 來自不可信來源，實際輸出 HTML 前應進行適當的 HTML 跳脫；原程式用 `escape_html()` 處理屬性與文字內容。

### 例子三：回傳布林值

```rust
fn is_heading_level(level: usize) -> bool {
    (1..=3).contains(&level)
}
```

`1..=3` 是包含 3 的範圍，`contains()` 判斷數值是否位於範圍內。

## 2.2 借用與參考：`&T`、`&mut T`

Rust 的參考讓函式可以存取資料，而不必取得所有權：

- `&T`：不可變參考，可讀取資料。
- `&mut T`：可變參考，可修改所參考的資料。
- 在同一時間，Rust 會限制對同一資料的參考方式，避免資料競爭與不安全的別名修改。

原程式 `render_nav_nodes(nodes: &[NavNode], pages: &[Page], output: &mut String)` 同時展示兩種方式：`nodes`、`pages` 是不可變切片，`output` 是可修改的字串參考。

### 例子一：只讀取字串

```rust
fn print_title(title: &str) {
    println!("{title}");
}

let title = String::from("安裝說明");
print_title(&title);
println!("{title}"); // 呼叫後仍可使用 title
```

函式借用 `title`，沒有把它移走。

### 例子二：透過可變參考追加內容

```rust
fn append_suffix(text: &mut String) {
    text.push_str(".html");
}

let mut filename = String::from("index");
append_suffix(&mut filename);
assert_eq!(filename, "index.html");
```

因為函式會修改字串，呼叫端變數必須可變，並傳入 `&mut filename`。

### 例子三：用切片讀取多個頁面

```rust
fn print_pages(titles: &[String]) {
    for title in titles {
        println!("{title}");
    }
}

let titles = vec![
    "首頁".to_string(),
    "安裝".to_string(),
];
print_pages(&titles);
```

`&[String]` 是字串向量的不可變切片。函式可接受 `Vec<String>` 的借用，也可接受其他連續字串資料的切片，因此介面比直接要求 `&Vec<String>` 更彈性。

## 2.3 生命週期：參考能有效使用多久

生命週期描述參考有效的範圍。編譯器通常能自動推導，不需要每個函式都明寫 `'a`。當回傳參考的來源不明顯，或函式有多個參考參數時，才常需要生命週期註記。

例如：

```rust
fn first_title<'a>(titles: &'a [String]) -> Option<&'a str> {
    titles.first().map(|title| title.as_str())
}
```

`'a` 是生命週期參數名稱，不是執行時的變數。這表示回傳的 `&str` 不會比輸入切片所借用的資料活得更久。`Option` 則代表可能沒有第一個元素。

### 例子一：回傳輸入字串的一部分

```rust
fn first_word<'a>(text: &'a str) -> &'a str {
    text.split_whitespace().next().unwrap_or("")
}
```

回傳字串切片仍借用原始 `text` 的內容，不會另行配置一個 `String`。

### 例子二：從結構體借用欄位

```rust
struct PageRef<'a> {
    title: &'a str,
}

let title = String::from("首頁");
let page = PageRef { title: &title };
println!("{}", page.title);
```

`PageRef` 不擁有標題字串，而是借用外部字串，因此結構體需要生命週期註記。`title` 必須比 `page` 的借用使用期間活得久。

### 例子三：兩個輸入參考，明確指出回傳來源

```rust
fn longer<'a>(left: &'a str, right: &'a str) -> &'a str {
    if left.len() >= right.len() { left } else { right }
}
```

此簽章要求兩個參考都能配合同一個 `'a`，回傳值也不會超過這個生命週期。若兩個輸入的生命週期不同，呼叫端可用的回傳生命週期會受到較短者限制。

## 2.4 `Result`、`Error` 與 `?`

原程式的函式常見這種簽章：

```rust
fn parse_pages(input: &str) -> Result<Vec<Page>, Box<dyn Error>>
```

- `Result<T, E>`：成功時是 `Ok(T)`，失敗時是 `Err(E)`。
- `Box<dyn Error>`：用 trait object 包裝不同的錯誤型別，方便同一函式回傳多種錯誤。
- `?`：若運算成功，取出成功值繼續執行；若失敗，將錯誤轉換成相容型別並提早回傳。

`?` 不是忽略錯誤，而是把錯誤往呼叫端傳遞。最外層再決定要顯示、記錄或結束程式。

### 例子一：讀取文字檔

```rust
use std::{error::Error, fs};

fn read_text(path: &str) -> Result<String, Box<dyn Error>> {
    let text = fs::read_to_string(path)?;
    Ok(text)
}
```

檔案不存在、權限不足或內容不是有效 UTF-8 時，讀取可能失敗；`?` 會把錯誤傳回呼叫端。

### 例子二：解析數字

```rust
fn parse_level(text: &str) -> Result<usize, std::num::ParseIntError> {
    let level = text.parse::<usize>()?;
    Ok(level)
}
```

這裡回傳具體錯誤型別 `ParseIntError`，比 `Box<dyn Error>` 更精確。

### 例子三：呼叫端處理錯誤

```rust
fn run() -> Result<(), Box<dyn std::error::Error>> {
    let text = std::fs::read_to_string("config/content.htm")?;
    println!("讀入 {} 個位元組", text.len());
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("執行失敗：{error}");
        std::process::exit(1);
    }
}
```

這與原程式 `main()` 中的錯誤處理方式相近。錯誤輸出到標準錯誤串流，結束碼 `1` 表示失敗。

---

# 第三章：正規表示式、閉包、迭代器、字串處理與檔名衝突

## 3.1 正規表示式（Regex）

原程式：

```rust
let heading_re = Regex::new(r"(?is)<h([1-3])\b[^>]*>.*?</h[1-3]\s*>")?;
```

`Regex::new()` 編譯正規表示式，結果是 `Result`，所以可用 `?`。此模式使用：

- `(?i)`：忽略大小寫。
- `(?s)`：讓 `.` 可以匹配換行。
- `<h([1-3])`：匹配 h1、h2、h3，並擷取數字。
- `\b`：字元邊界。
- `[^>]*`：匹配標籤屬性中的非 `>` 字元。
- `.*?`：非貪婪匹配標題內文。
- `\s*`：允許結尾標籤前有空白。

注意：以正規表示式解析一般 HTML 只適用於格式受控、結構簡單的來源。HTML 有巢狀結構、註解、script 內容及不規則標記等情況；若來源更複雜，應考慮 HTML parser。原程式是針對既定 CMS 內容格式的轉換工具。

### 例子一：找出所有 h1/h2/h3

```rust
use regex::Regex;

let re = Regex::new(r"(?i)<h[1-3]\b[^>]*>.*?</h[1-3]\s*>")?;
for heading in re.find_iter("<h1>首頁</h1><h2>安裝</h2>") {
    println!("{}", heading.as_str());
}
```

將這段放進回傳 `Result` 的函式中，就可以使用 `?`。

### 例子二：移除 HTML 標籤

```rust
use regex::Regex;

let tag_re = Regex::new(r"(?s)<[^>]*>")?;
let text = tag_re.replace_all("<p>歡迎 <b>使用</b></p>", "");
assert_eq!(text, "歡迎 使用");
```

`replace_all()` 會回傳 `Cow<str>`（可能借用原字串，也可能擁有新字串），不一定立即配置新字串。

### 例子三：擷取標題層級

```rust
use regex::Regex;

let re = Regex::new(r"(?i)^<h([1-3])\b[^>]*>")?;
if let Some(captures) = re.captures("<h2 class=\"chapter\">安裝</h2>") {
    let level = captures[1].parse::<usize>()?;
    println!("層級：{level}");
}
```

`captures[1]` 是第一個括號分組的內容；解析成數字時仍應處理可能的解析錯誤。

## 3.2 閉包（closure）

原程式中的閉包：

```rust
.map(|c| {
    if invalid.contains(&c) || c.is_control() {
        '_'
    } else {
        c
    }
})
```

`|c| { ... }` 定義匿名函式。閉包可接收參數、回傳值，也可以捕獲周圍環境中的變數。此例捕獲 `invalid`，逐字元判斷是否需要替換。

### 例子一：將標題轉成大寫

```rust
let titles = vec!["home", "install"];
let upper: Vec<String> = titles
    .iter()
    .map(|title| title.to_uppercase())
    .collect();
```

`map()` 對每個元素執行閉包，並產生新序列。

### 例子二：篩選副檔名

```rust
let files = vec!["a.html", "b.css", "c.html"];
let html_files: Vec<&str> = files
    .into_iter()
    .filter(|name| name.ends_with(".html"))
    .collect();
```

`into_iter()` 會消耗 `files`，因此後面不能再使用原本的 `files`。若要保留它，可改用 `files.iter()`，並留意元素會是參考。

### 例子三：捕獲外部變數

```rust
let prefix = "page-";
let names: Vec<String> = (1..=3)
    .map(|n| format!("{prefix}{n}.html"))
    .collect();
```

閉包讀取外部的 `prefix`，並產生 `page-1.html` 到 `page-3.html`。

## 3.3 迭代器：`iter`、`enumerate`、`filter`、`collect`

原程式：

```rust
for (index, page) in pages.iter().enumerate() {
    // ...
}
```

- `iter()`：借用集合中的元素。
- `enumerate()`：額外提供從 0 開始的索引。
- `find_iter()`：是 Regex 的迭代搜尋方法。
- `filter()`：保留符合條件的項目。
- `map()`：轉換每個項目。
- `collect()`：把迭代結果收集成向量、集合等目標型別。

### 例子一：產生頁面序號

```rust
let titles = ["首頁", "安裝", "參考"];
for (index, title) in titles.iter().enumerate() {
    println!("第 {} 頁：{}", index + 1, title);
}
```

Rust 集合索引通常從 0 開始；面向使用者顯示時常用 `index + 1`。

### 例子二：產生檔名清單

```rust
let filenames: Vec<String> = ["首頁", "安裝"]
    .iter()
    .map(|title| format!("{title}.html"))
    .collect();
```

### 例子三：只保留 h1 分頁

```rust
let pages = vec![
    ("首頁".to_string(), 1_usize),
    ("安裝".to_string(), 2),
    ("參考".to_string(), 1),
];
let roots: Vec<_> = pages
    .iter()
    .filter(|(_, level)| *level == 1)
    .collect();
```

`filter()` 的條件通常接收對元素的參考，所以此例使用 `*level` 讀取實際數值。

## 3.4 字串處理與 HTML 跳脫

原程式的 `escape_html()` 依序替換 `&`、`<`、`>`、`"`、`'`。替換順序很重要：應先把 `&` 轉成 `&amp;`，否則後續新增的 `&lt;` 可能再次被替換。

`slug_filename()` 則用 `trim()`、`chars()`、`map()`、`collect()` 以及 `trim_end_matches()` 清理檔名。

### 例子一：修剪使用者輸入

```rust
let title = "  安裝說明  ";
let normalized = title.trim();
assert_eq!(normalized, "安裝說明");
```

`trim()` 回傳借用的字串切片，不會修改原始 `String`。

### 例子二：將特殊字元轉成 HTML entity

```rust
fn escape_text(input: &str) -> String {
    input
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&#39;")
}
```

這可用於 HTML 文字或屬性中的基本跳脫。若要處理 JavaScript、CSS 或 URL，不能直接把 HTML 跳脫當成通用防護；每種輸出情境需要相應的編碼方式。

### 例子三：清理路徑名稱

```rust
fn safe_name(input: &str) -> String {
    input
        .chars()
        .map(|c| {
            if ['<', '>', ':', '"', '/', '\\', '|', '?', '*'].contains(&c)
                || c.is_control()
            {
                '_'
            } else {
                c
            }
        })
        .collect()
}
```

這只是基本的非法字元清理。實際檔名還要考慮空字串、保留名稱、路徑長度、大小寫衝突與目錄穿越等問題。

## 3.5 檔名衝突處理

原程式使用兩個 `HashMap`：

- `title_counts`：相同標題加上 `-2`、`-3` 等序號。
- `filename_counts`：再以小寫檔名為鍵，避免不同標題清理後產生同一檔名。

例如標題重複時可能產生 `介紹-1.html`、`介紹-2.html`；不同標題清理後若都變成相同檔名，第二層計數可再附加序號。

### 例子一：對重複標題編號

```rust
use std::collections::HashMap;

let mut counts = HashMap::<String, usize>::new();
let title = "介紹";

let n = counts.entry(title.to_string()).or_insert(0);
*n += 1;
let unique = if *n == 1 {
    title.to_string()
} else {
    format!("{title}-{}", *n)
};
```

### 例子二：不分大小寫檢查衝突

```rust
use std::collections::HashSet;

let mut used = HashSet::new();
for filename in ["Guide.html", "guide.html"] {
    let key = filename.to_lowercase();
    if !used.insert(key) {
        println!("發現忽略大小寫後的檔名衝突：{filename}");
    }
}
```

這個例子使用 `HashSet` 保存已使用的鍵；`insert()` 回傳 `false` 代表該鍵已存在。

### 例子三：依衝突次數產生檔名

```rust
use std::collections::HashMap;

fn unique_filename(base: &str, counts: &mut HashMap<String, usize>) -> String {
    let key = base.to_lowercase();
    let count = counts.entry(key).or_insert(0);
    *count += 1;

    if *count == 1 {
        format!("{base}.html")
    } else {
        format!("{base}-{}.html", *count)
    }
}
```

這是簡化範例。若 `base` 本身含有 `.html`，應先將「基底名稱」與「副檔名」分開處理；原程式的 `base_name` 就是在加上 `.html` 前先完成清理。

---

# 第四章：HTML 樣板、CSS 排版、樹狀導覽與 Previous／Next

## 4.1 HTML 樣板與 `format!`

原程式 `html_header(title)` 使用 `format!()` 將 HTML 樣板轉成 `String`，並以 `{title}` 插入頁面標題。因為 HTML、CSS、JavaScript 本身大量使用大括號，所以樣板中的 CSS/JavaScript 大括號要寫成 `{{`、`}}`，表示輸出單一大括號。

原程式使用 `r##" ... "##` raw string。raw string 不會把反斜線當作一般跳脫字元，且 `##` 讓內容可包含一般的 `"#` 組合而不會過早結束字串。

### 例子一：建立簡單 HTML 文件

```rust
fn simple_html(title: &str, body: &str) -> String {
    format!(
        r#"<!doctype html>
<html lang="zh-Hant">
<head><meta charset="utf-8"><title>{}</title></head>
<body>{}</body>
</html>"#,
        title, body
    )
}
```

此例只示範模板插值。實際應用要依輸出位置跳脫 `title` 與 `body`，不能直接將任意使用者輸入插入 HTML。

### 例子二：模板中的 CSS 大括號

```rust
let html = format!(
    r#"<style>
body {{ margin: 0; padding: 1rem; }}
</style>
<h1>{}</h1>"#,
    "首頁"
);
```

在 `format!` 格式字串裡，`{{` 和 `}}` 代表輸出字面上的 `{` 和 `}`。

### 例子三：使用命名參數

```rust
let title = "網站地圖";
let html = format!("<title>{page_title}</title>", page_title = title);
```

命名參數可讓大型模板更容易閱讀；若模板含有不可信文字，仍應先依 HTML 上下文跳脫。

## 4.2 CSS Flexbox：Previous 靠左、Next 靠右

原程式的 `.page-navigation` 使用：

```css
.page-navigation {
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
    width: 100%;
    gap: 20px;
}
```

- `display: flex`：讓子元素成為 Flex 項目。
- `flex-direction: row`：子項目沿水平方向排列。
- `justify-content: space-between`：將可用空間放在子項目之間，第一個靠左、最後一個靠右。
- `.previous` 與 `.next` 各佔約一半寬度，並分別使用左、右文字對齊。
- 第一頁仍輸出空的 `.previous`，最後一頁仍輸出空的 `.next`，因此版面不會因少一個連結而失去左右配置。

### 例子一：左右兩側按鈕

```html
<div class="toolbar">
  <button>Previous</button>
  <button>Next</button>
</div>
```

```css
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}
```

### 例子二：讓左右欄位等寬

```css
.previous,
.next {
  flex: 1 1 50%;
  min-width: 0;
}
.previous { text-align: left; }
.next { text-align: right; }
```

`min-width: 0` 可避免 Flex 子項目的最小內容寬度造成溢出；長標題還可以搭配 `overflow-wrap: anywhere`。

### 例子三：小螢幕改成垂直排列

```css
@media (max-width: 480px) {
  .page-navigation {
    flex-direction: column;
    align-items: stretch;
  }
  .page-navigation .previous,
  .page-navigation .next {
    flex: 1 1 auto;
    width: 100%;
  }
  .page-navigation .next {
    text-align: right;
  }
}
```

這個延伸例子會在小螢幕將導覽項目改成上下排列。若需求是所有螢幕都必須左右分開，便不應套用這個 media query。

## 4.3 樹狀導覽：遞迴與節點

原程式的節點：

```rust
struct NavNode {
    page_index: usize,
    children: Vec<NavNode>,
}
```

每個節點記錄一個分頁索引，並有一個子節點向量。`insert_nav_node()` 會依標題層級決定把節點放在目前層，或遞迴進入最後一個節點的 `children`。`render_nav_nodes()` 再以遞迴方式將節點轉成巢狀 `<ul>` 與 `<li>`。

這種方式適合來源本身按 h1、h2、h3 順序排列的簡化文件。它不是完整的 HTML 大綱演算法：例如跳過層級、在多個 h1 之間切換章節等情況，可能需要更明確的樹狀規則。

### 例子一：建立單一根節點

```rust
let tree = vec![NavNode {
    page_index: 0,
    children: vec![],
}];
```

這表示樹中有一個節點，指向 `pages[0]`，沒有子節點。

### 例子二：建立父子節點

```rust
let tree = vec![NavNode {
    page_index: 0,
    children: vec![
        NavNode {
            page_index: 1,
            children: vec![],
        },
        NavNode {
            page_index: 2,
            children: vec![],
        },
    ],
}];
```

這是以第 0 頁為父節點、第 1 與第 2 頁為子節點的示範結構。

### 例子三：遞迴計算節點數

```rust
fn count_nodes(nodes: &[NavNode]) -> usize {
    nodes.iter()
        .map(|node| 1 + count_nodes(&node.children))
        .sum()
}
```

每個節點先計 1，再加上所有子節點的數量。遞迴函式需要有自然的終止條件；空切片時 `sum()` 結果為 0，因此此例可終止。

## 4.4 產生導覽 HTML 與 Previous／Next

原程式的 `render_nav_nodes()` 會：

1. 依 `page_index` 取得對應的 `Page`。
2. 根據是否有子節點選擇 `<li>` 的 class。
3. 使用 `escape_html()` 跳脫檔名與標題。
4. 有子節點時輸出 `<ul class="dropdown">`，再遞迴輸出子節點。

`render_previous_next(index, pages)` 使用索引判斷前後頁：

- 若 `index > 0`，前一頁是 `pages[index - 1]`。
- 若 `index + 1 < pages.len()`，下一頁是 `pages[index + 1]`。
- 第一頁與最後一頁仍輸出空容器，以配合 Flexbox 左右對齊。

### 例子一：安全地建立連結

```rust
fn anchor(filename: &str, title: &str) -> String {
    format!(
        "<a href=\"{}\">{}</a>",
        escape_html(filename),
        escape_html(title)
    )
}
```

檔名放在 HTML 屬性中，標題放在 HTML 文字內容中；兩處都要跳脫。這個 helper 沿用原程式的 `escape_html()`。

### 例子二：判斷是否存在上一頁

```rust
fn previous_title(index: usize, titles: &[String]) -> Option<&str> {
    if index > 0 {
        Some(titles[index - 1].as_str())
    } else {
        None
    }
}
```

此簽章在實際 Rust 編譯時會遇到回傳參考生命週期需要明確關聯的情況；可寫成：

```rust
fn previous_title<'a>(index: usize, titles: &'a [String]) -> Option<&'a str> {
    if index > 0 {
        Some(titles[index - 1].as_str())
    } else {
        None
    }
}
```

### 例子三：安全地取得下一頁

```rust
fn next_filename(index: usize, filenames: &[String]) -> Option<&str> {
    filenames.get(index + 1).map(|name| name.as_str())
}
```

正式簽章同樣應把回傳參考的生命週期與 `filenames` 關聯：

```rust
fn next_filename<'a>(index: usize, filenames: &'a [String]) -> Option<&'a str> {
    filenames.get(index + 1).map(|name| name.as_str())
}
```

使用 `get()` 可在索引超出範圍時回傳 `None`，比直接索引更不容易因錯誤索引而 panic。

---

# 第五章：檔案讀寫、JSON 序列化、命令列參數與 `main()`

## 5.1 檔案讀寫與路徑

原程式 `generate(input_path, output_dir)` 使用：

```rust
let input = fs::read_to_string(input_path)?;
fs::create_dir_all(output_dir)?;
fs::write(output_dir.join("index.html"), render_index(&pages))?;
```

- `read_to_string()`：讀取 UTF-8 文字檔。
- `create_dir_all()`：建立目錄及不存在的中間層目錄。
- `Path::join()`：以平台合適的方式組合路徑。
- `write()`：建立檔案或覆寫既有檔案。
- `?`：任何 I/O 錯誤都向呼叫端傳回。

### 例子一：讀取文字設定

```rust
use std::fs;

let config_text = fs::read_to_string("config/content.htm")?;
println!("讀入 {} 個位元組", config_text.len());
```

需放在可使用 `?` 的函式中，例如回傳 `Result` 的 `run()`。

### 例子二：建立輸出目錄並寫檔

```rust
use std::{fs, path::Path};

let output_dir = Path::new("content");
fs::create_dir_all(output_dir)?;
fs::write(output_dir.join("hello.txt"), "Hello Rust\n")?;
```

這會建立 `content` 目錄（若尚不存在），再寫入 `hello.txt`。

### 例子三：逐行讀取大型文字檔

```rust
use std::{fs::File, io::{self, BufRead, BufReader}};

fn print_lines(path: &str) -> io::Result<()> {
    let file = File::open(path)?;
    for line in BufReader::new(file).lines() {
        println!("{}", line?);
    }
    Ok(())
}
```

相較一次將整份檔案讀進 `String`，逐行讀取可以降低大型檔案的記憶體需求。`lines()` 每次產生一個 `Result<String, io::Error>`，所以每行也要處理錯誤。

## 5.2 JSON 序列化

原程式先將 `SearchPage` 組成 `Vec<SearchPage>`，再呼叫：

```rust
let search_json = serde_json::to_string(&search_pages)?;
let search_js = format!(
    "var tipuesearch = {{\"pages\": {}}};\n",
    search_json
);
```

`serde_json::to_string()` 把可序列化資料轉成 JSON 字串。外層 JavaScript 的 `{`、`}` 在 `format!` 中必須寫成 `{{`、`}}`。JSON 字串不是任意文字拼接的替代品：資料應交給序列化器，避免自行處理引號、反斜線等跳脫細節。

### 例子一：序列化向量

```rust
let numbers = vec![1, 2, 3];
let json = serde_json::to_string(&numbers)?;
assert_eq!(json, "[1,2,3]");
```

### 例子二：序列化結構體

```rust
use serde::Serialize;

#[derive(Serialize)]
struct MenuItem {
    title: String,
    href: String,
}

let item = MenuItem {
    title: "首頁".to_string(),
    href: "index.html".to_string(),
};
let json = serde_json::to_string(&item)?;
```

### 例子三：將 JSON 寫入檔案

```rust
let data = vec![
    ("首頁", "index.html"),
    ("網站地圖", "sitemap.html"),
];
let json = serde_json::to_string(&data)?;
std::fs::write("content/menu.json", json)?;
```

若要讓 JSON 更容易人工閱讀，可使用 `serde_json::to_string_pretty()`。

## 5.3 命令列參數

原程式：

```rust
let args: Vec<String> = env::args().collect();

let input = args.get(1)
    .map(PathBuf::from)
    .unwrap_or_else(|| PathBuf::from("config").join("content.htm"));

let output = args.get(2)
    .map(PathBuf::from)
    .unwrap_or_else(|| PathBuf::from("content"));
```

- `env::args()` 取得命令列參數的迭代器。
- `collect()` 收集成 `Vec<String>`。
- `get(1)` 安全取得第二個參數；`get(0)` 通常是程式名稱。
- `map(PathBuf::from)` 將參數字串轉成路徑。
- `unwrap_or_else(...)` 在沒有提供參數時，才執行閉包產生預設值。

### 例子一：取得一個參數

```rust
let args: Vec<String> = std::env::args().collect();
if let Some(filename) = args.get(1) {
    println!("輸入檔：{filename}");
}
```

### 例子二：有預設值的輸出目錄

```rust
use std::path::PathBuf;

let args: Vec<String> = std::env::args().collect();
let output_dir = args.get(1)
    .map(PathBuf::from)
    .unwrap_or_else(|| PathBuf::from("content"));
```

### 例子三：支援 `--help`

```rust
let args: Vec<String> = std::env::args().collect();
if args.iter().any(|arg| arg == "--help" || arg == "-h") {
    println!("用法：convert.exe [輸入檔] [輸出目錄]");
    return;
}
```

`any()` 只要找到一個符合條件的元素就回傳 `true`。這適合簡單工具；參數複雜時可考慮使用專門的命令列解析 crate。

## 5.4 `main()`：程式進入點與錯誤出口

Rust 執行檔從 `fn main()` 開始。原程式的 `main()` 做三件事：

1. 取得命令列引數。
2. 若有 `--help` 或 `-h`，顯示用法後 `return`。
3. 呼叫 `generate()`；若得到 `Err`，用 `eprintln!()` 顯示錯誤並以 `exit(1)` 結束。

### 例子一：最簡單的入口

```rust
fn main() {
    println!("開始轉換");
}
```

### 例子二：把工作交給 `run()`

```rust
fn run() -> Result<(), Box<dyn std::error::Error>> {
    println!("執行主要工作");
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("錯誤：{error}");
        std::process::exit(1);
    }
}
```

將主要流程放進 `run()`，可以讓 `run()` 使用 `?`，也使 `main()` 專注於程序入口及錯誤顯示。

### 例子三：回傳作業系統結束碼

```rust
use std::process::ExitCode;

fn main() -> ExitCode {
    match std::fs::read_to_string("config/content.htm") {
        Ok(_) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("讀取失敗：{error}");
            ExitCode::FAILURE
        }
    }
}
```

`ExitCode::SUCCESS` 與 `ExitCode::FAILURE` 用來表達成功或失敗。此寫法與原程式的 `std::process::exit(1)` 是不同但相關的方式。

---

# 第六章：把函式串起來理解整體程式

原程式的主要呼叫關係可以整理成：

```text
main()
 └─ generate(input_path, output_dir)
     ├─ fs::read_to_string()
     ├─ parse_pages()
     │   ├─ Regex::new() / find_iter()
     │   ├─ strip_tags()
     │   └─ slug_filename()
     ├─ render_index()
     │   └─ render_page()
     │       ├─ html_header()
     │       ├─ navigation_links()
     │       │   ├─ build_navigation_tree()
     │       │   │   └─ insert_nav_node()
     │       │   └─ render_nav_nodes()
     │       ├─ render_previous_next()
     │       ├─ fix_static_paths()
     │       └─ html_footer()
     ├─ render_sitemap()
     ├─ 建立 SearchPage 清單
     ├─ serde_json::to_string()
     └─ fs::write()
```

學習時可以把每個函式視為一個小任務：

- **解析函式**：輸入文字，回傳結構化資料。
- **資料整理函式**：清理標題、建立檔名、處理衝突。
- **渲染函式**：把資料轉成 HTML 字串。
- **輸出函式**：把字串寫入磁碟。
- **入口函式**：處理使用者參數、呼叫主要流程、呈現錯誤。

這樣的分工可以降低單一函式的複雜度，也更容易替個別函式寫測試。

## 建議練習順序

1. 修改 `slug_filename()`，增加對空白標題的測試。
2. 為 `parse_pages()` 加入「沒有任何標題」的錯誤測試。
3. 測試重複標題會產生不同檔名。
4. 測試第一頁沒有 Previous、最後一頁沒有 Next。
5. 加入一個新的 `SearchPage` 欄位，確認 JSON 輸出也包含它。
6. 讓 `main()` 支援第三個參數，例如指定是否產生網站地圖。
7. 將 HTML 產生函式與檔案寫入函式分開測試。

## 建置提示

原程式使用 `regex`、`serde` 與 `serde_json`。`Cargo.toml` 至少需要類似：

```toml
[dependencies]
regex = "1"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
```

在專案根目錄執行：

```bash
cargo check
cargo run
cargo run -- config/content.htm content
cargo run -- --help
```

若是在 Windows 已編譯的 `convert.exe`，可使用：

```bat
convert.exe
convert.exe config\content.htm content
convert.exe --help
```

提醒：這份教材的程式片段是教學用延伸例子，不是全部都能直接貼在同一個作用域中。若複製片段，請確認 `use` 宣告、函式位置、回傳型別與相依 crate 都符合所在專案。
