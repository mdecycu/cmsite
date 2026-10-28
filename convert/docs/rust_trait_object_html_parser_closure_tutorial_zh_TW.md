# Rust 進階程式教材：Trait Object、HTML Parser 與閉包

本教材以 Rust HTML 轉換器為背景，說明如何讓不同元件共用介面、正確解析
HTML 結構，以及把可重用的處理邏輯以閉包傳遞。每個主題各有五個實用範例。

## 建議依賴

在 `Cargo.toml` 中加入：

``` toml
[dependencies]
scraper = "0.22"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
```

範例多為獨立片段；請勿把多個同名 `main()` 全貼進同一個檔案。HTML parser
範例使用 `scraper` crate。

------------------------------------------------------------------------

# 第一章：Trait Object（特徵物件）

## 1.1 Trait 與 Trait Object 的概念

`trait` 定義一組行為契約。型別實作 trait
後，呼叫端就能透過該介面使用它，而不必知道具體型別。

``` rust
trait Render {
    fn render(&self) -> String;
}

struct HtmlPage {
    title: String,
}

impl Render for HtmlPage {
    fn render(&self) -> String {
        format!("<h1>{}</h1>", self.title)
    }
}
```

-   `trait Render` 宣告行為。
-   `impl Render for HtmlPage` 為 `HtmlPage` 實作該行為。
-   `&self` 代表以不可變參考借用物件。
-   `String` 是擁有所有權、可增長的字串。

Trait object 使用 `dyn Trait` 表示執行時具體型別可以不同，例如：

``` rust
let item: Box<dyn Render> = Box::new(HtmlPage {
    title: "Rust 教材".to_string(),
});
println!("{}", item.render());
```

`Box<T>` 是擁有 heap 上資料的智慧指標。`dyn Render`
的具體型別大小在編譯時未知，因此常透過 `Box<dyn Render>` 或
`&dyn Render` 使用。方法呼叫會採用動態派發，經由 vtable
呼叫實際型別的實作。

### 泛型與 Trait Object

``` rust
fn render_static<T: Render>(item: &T) {
    println!("{}", item.render());
}

fn render_dynamic(item: &dyn Render) {
    println!("{}", item.render());
}
```

`T: Render`
通常使用靜態派發，編譯器依具體型別產生對應程式碼；`&dyn Render`
使用動態派發。泛型通常有利於內聯，但可能增加程式碼量；trait object
能在同一集合中混合不同實作。實際效能需依程式量測，不應一概而論。

並非每個 trait 都能形成 `dyn Trait`。Trait 必須符合 dyn
compatibility（舊稱 object safety）規則。泛型方法通常不能透過 trait
object 動態呼叫；若某方法只適用於具體型別，可用 `where Self: Sized`
限定它。

``` rust
trait Plugin {
    fn name(&self) -> &str;

    fn clone_concrete(&self) -> Self
    where
        Self: Sized;
}
```

`Box<dyn Plugin>` 可呼叫 `name()`，但不能透過 trait object 呼叫要求
`Self: Sized` 的 `clone_concrete()`。

## 範例 1：不同 HTML 元件使用同一個輸出介面

``` rust
trait HtmlComponent {
    fn render(&self) -> String;
}

struct Paragraph { text: String }
struct Warning { message: String }

fn escape_html(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&#39;")
}

impl HtmlComponent for Paragraph {
    fn render(&self) -> String {
        format!("<p>{}</p>", escape_html(&self.text))
    }
}

impl HtmlComponent for Warning {
    fn render(&self) -> String {
        format!("<aside class=\"warning\">{}</aside>", escape_html(&self.message))
    }
}

fn main() {
    let parts: Vec<Box<dyn HtmlComponent>> = vec![
        Box::new(Paragraph { text: "歡迎使用 Rust".into() }),
        Box::new(Warning { message: "請先備份檔案".into() }),
    ];

    for part in &parts {
        println!("{}", part.render());
    }
}
```

**解說：** `Paragraph` 與 `Warning` 型別不同，但都實作
`HtmlComponent`。`Vec<Box<dyn HtmlComponent>>`
因此能存放兩種元件，迴圈只需呼叫 `render()`。若新增
`CodeBlock`，只要實作 trait，不必改動迴圈。此例的跳脫函式適用於簡單 HTML
文字內容；不同輸出上下文仍需採用正確的編碼方式。

## 範例 2：可替換的輸出目的地

``` rust
use std::{fs, io};

trait OutputSink {
    fn write_output(&self, content: &str) -> io::Result<()>;
}

struct FileSink { path: String }
struct ConsoleSink;

impl OutputSink for FileSink {
    fn write_output(&self, content: &str) -> io::Result<()> {
        fs::write(&self.path, content)
    }
}

impl OutputSink for ConsoleSink {
    fn write_output(&self, content: &str) -> io::Result<()> {
        println!("{content}");
        Ok(())
    }
}

fn publish(sink: &dyn OutputSink, html: &str) -> io::Result<()> {
    sink.write_output(html)
}

fn main() -> io::Result<()> {
    let file = FileSink { path: "preview.html".into() };
    publish(&file, "<h1>預覽</h1>")?;
    publish(&ConsoleSink, "已產生預覽");
    Ok(())
}
```

**解說：** `OutputSink` 隔離「要輸出什麼」與「輸出到哪裡」。`FileSink`
寫入檔案，`ConsoleSink` 顯示在終端機。`io::Result<()>`
表示成功時沒有額外資料，失敗時回傳 I/O
錯誤。正式程式若要檢查標準輸出錯誤，可改用 `std::io::Write`。

## 範例 3：可插拔的輸入驗證規則

``` rust
trait Validator {
    fn validate(&self, input: &str) -> Result<(), String>;
}

struct NotEmpty;
struct HasHeading;
struct MaxBytes { limit: usize }

impl Validator for NotEmpty {
    fn validate(&self, input: &str) -> Result<(), String> {
        if input.trim().is_empty() {
            Err("輸入內容不可為空".into())
        } else { Ok(()) }
    }
}

impl Validator for HasHeading {
    fn validate(&self, input: &str) -> Result<(), String> {
        if ["<h1", "<h2", "<h3"].iter().any(|tag| input.contains(tag)) {
            Ok(())
        } else {
            Err("找不到 h1、h2 或 h3 標題".into())
        }
    }
}

impl Validator for MaxBytes {
    fn validate(&self, input: &str) -> Result<(), String> {
        if input.len() <= self.limit {
            Ok(())
        } else {
            Err(format!("內容超過 {} bytes", self.limit))
        }
    }
}

fn validate_all(rules: &[Box<dyn Validator>], input: &str) -> Result<(), String> {
    for rule in rules {
        rule.validate(input)?;
    }
    Ok(())
}

fn main() {
    let rules: Vec<Box<dyn Validator>> = vec![
        Box::new(NotEmpty),
        Box::new(HasHeading),
        Box::new(MaxBytes { limit: 100_000 }),
    ];
    println!("{:?}", validate_all(&rules, "<h1>教材</h1>"));
}
```

**解說：** 每個 validator 負責一項規則，`validate_all()`
不需知道具體型別。`?` 讓第一個錯誤立即回傳。`HasHeading`
的字串搜尋只是教學示範；真正的 HTML 檢查應使用 parser，而不是只用
`contains()`。

## 範例 4：可插拔的文字處理步驟

``` rust
trait TextTransform {
    fn apply(&self, input: &str) -> String;
}

struct TrimText;
struct AddComment { label: String }

impl TextTransform for TrimText {
    fn apply(&self, input: &str) -> String {
        input.trim().to_string()
    }
}

impl TextTransform for AddComment {
    fn apply(&self, input: &str) -> String {
        format!("<!-- {} -->\n{}", self.label, input)
    }
}

fn transform_all(steps: &[Box<dyn TextTransform>], input: &str) -> String {
    steps.iter().fold(input.to_string(), |current, step| {
        step.apply(&current)
    })
}

fn main() {
    let steps: Vec<Box<dyn TextTransform>> = vec![
        Box::new(TrimText),
        Box::new(AddComment { label: "由 convert.exe 產生".into() }),
    ];
    println!("{}", transform_all(&steps, "\n<h1>首頁</h1>\n"));
}
```

**解說：** `fold()`
把前一步輸出交給下一步。處理順序會影響結果：先修剪空白，再加上註解。若處理步驟可能失敗，可將
`apply()` 改成回傳 `Result<String, ErrorType>`。

## 範例 5：不同搜尋索引格式共用介面

``` rust
use serde::Serialize;

#[derive(Serialize)]
struct SearchRecord {
    title: String,
    url: String,
}

trait SearchFormatter {
    fn format(&self, records: &[SearchRecord]) -> Result<String, String>;
}

struct PlainTextFormatter;
struct JsonFormatter;

impl SearchFormatter for PlainTextFormatter {
    fn format(&self, records: &[SearchRecord]) -> Result<String, String> {
        let mut out = String::new();
        for r in records {
            out.push_str(&format!("{}\t{}\n", r.title, r.url));
        }
        Ok(out)
    }
}

impl SearchFormatter for JsonFormatter {
    fn format(&self, records: &[SearchRecord]) -> Result<String, String> {
        serde_json::to_string_pretty(records).map_err(|e| e.to_string())
    }
}

fn export(formatter: &dyn SearchFormatter, records: &[SearchRecord])
    -> Result<String, String>
{
    formatter.format(records)
}
```

**使用方式：**

``` rust
let records = vec![
    SearchRecord { title: "首頁".into(), url: "index.html".into() },
];
let json = export(&JsonFormatter, &records)?;
let text = export(&PlainTextFormatter, &records)?;
```

**解說：** 呼叫端不必知道格式是 JSON 或純文字。JSON 由 `serde_json`
序列化，避免自行處理引號與反斜線。此例將錯誤轉成 `String`
以簡化教材；大型程式較適合定義錯誤型別。

### Trait Object 速查

-   `&dyn Trait`：借用已存在的物件。
-   `Box<dyn Trait>`：擁有一個具體型別未知的物件。
-   `Vec<Box<dyn Trait>>`：集合中可混合不同實作。
-   `T: Trait`：泛型約束，通常採靜態派發。
-   若變體固定且有限，`enum` 也可能比 trait object 更簡單。
-   不可直接使用一般形式的 `Vec<dyn Trait>`，因為 `dyn Trait`
    是動態大小型別。

------------------------------------------------------------------------

# 第二章：HTML Parser（HTML 解析器）

## 2.1 為何不應只靠正規表示式解析 HTML？

原轉換器可用 Regex 尋找
`<h1>`、`<h2>`、`<h3>`，這對格式受控的內容可能足夠。但 HTML
可能有屬性順序變化、大小寫差異、巢狀元素、註解、script/style
內容、字元實體或不完整標記。正規表示式適合找簡單文字模式，不是一般 HTML
結構解析器的替代品。

HTML parser
將輸入解析成節點樹，程式可以透過標籤、屬性、文字與父子關係查詢。本文使用
`scraper` crate：

``` rust
use scraper::{Html, Selector};

let document = Html::parse_document(source);
let selector = Selector::parse("h1, h2, h3")?;
for element in document.select(&selector) {
    println!("{}", element.text().collect::<String>());
}
```

`Html::parse_document()` 解析文件；`Selector::parse()` 解析 CSS
selector；`select()` 找出符合的節點；`text()` 取得文字節點，而不是原始
HTML。

## 範例 1：找出所有 h1、h2、h3 標題

``` rust
use scraper::{Html, Selector};

fn list_headings(source: &str) -> Result<(), Box<dyn std::error::Error>> {
    let document = Html::parse_document(source);
    let selector = Selector::parse("h1, h2, h3")?;

    for element in document.select(&selector) {
        let level = element.value().name();
        let title = element.text().collect::<String>();
        println!("{level}: {}", title.trim());
    }
    Ok(())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let html = r#"
        <h1>Rust 入門</h1>
        <p>前言</p>
        <h2 class="chapter">安裝</h2>
        <h3 id="windows">Windows</h3>
    "#;
    list_headings(html)
}
```

**解說：** selector 中的逗號表示符合其中任一標籤。`name()`
取得標籤名稱；`text()` 收集標題中的文字節點，即使標題內含 `<em>`
等巢狀元素也能取得其文字。這適合找出轉換器需要的標題清單。

## 範例 2：讀取標題的 id、class 與文字

``` rust
use scraper::{Html, Selector};

fn inspect(source: &str) -> Result<(), Box<dyn std::error::Error>> {
    let document = Html::parse_document(source);
    let selector = Selector::parse("h1, h2, h3")?;

    for element in document.select(&selector) {
        let tag = element.value().name();
        let id = element.value().attr("id").unwrap_or("");
        let class = element.value().attr("class").unwrap_or("");
        let text = element.text().collect::<String>();
        println!("tag={tag}, id={id}, class={class}, text={}", text.trim());
    }
    Ok(())
}
```

**解說：** `attr()` 回傳
`Option<&str>`，因為屬性可能不存在；`unwrap_or("")`
提供預設空字串。`class` 可能包含多個空白分隔的名稱，不應假設它只有一個
class。可利用標題 `id` 產生錨點，或依 class 決定是否切頁。

## 範例 3：只抽取 main 區域中的標題

``` rust
use scraper::{Html, Selector};

fn main_headings(source: &str) -> Result<Vec<String>, Box<dyn std::error::Error>> {
    let document = Html::parse_document(source);
    let selector = Selector::parse("main h1, main h2, main h3")?;

    let headings = document
        .select(&selector)
        .map(|el| el.text().collect::<String>().trim().to_string())
        .collect();
    Ok(headings)
}
```

**解說：** `main h1` 表示 `main` 後代中的
`h1`。這能排除頁首、側欄等共用區塊的標題。`map()` 把元素轉成
`String`，`collect()` 依回傳型別推導成 `Vec<String>`。

## 範例 4：抽取連結文字與 href

``` rust
use scraper::{Html, Selector};

fn list_links(source: &str) -> Result<Vec<(String, String)>, Box<dyn std::error::Error>> {
    let document = Html::parse_document(source);
    let selector = Selector::parse("a[href]")?;

    let links = document
        .select(&selector)
        .filter_map(|el| {
            let href = el.value().attr("href")?;
            let text = el.text().collect::<String>();
            Some((text.trim().to_string(), href.to_string()))
        })
        .collect();

    Ok(links)
}
```

**解說：** `a[href]` 選取有 `href` 的連結。`filter_map()`
可以略過沒有值的節點。這裡只取得原始 `href`，沒有解析相對
URL。要把相對網址轉成絕對網址，必須提供 base URL，並用 URL parser
正確處理；不要只用字串串接。

## 範例 5：抽取 main 的純文字

``` rust
use scraper::{Html, Selector};

fn extract_main_text(source: &str) -> Result<String, Box<dyn std::error::Error>> {
    let document = Html::parse_document(source);
    let selector = Selector::parse("main")?;

    let Some(main) = document.select(&selector).next() else {
        return Ok(String::new());
    };

    let text = main.text().collect::<Vec<_>>().join(" ");
    Ok(text.split_whitespace().collect::<Vec<_>>().join(" "))
}
```

**解說：** `next()` 取第一個 `main`；若不存在，let-else
就回傳空字串。`text()` 只取得文字，不保留 `<p>`、`<img>`、`<table>`
等標記。`split_whitespace()` 可將多餘空白整理成單一空格。

### Parser 與轉換器整合時的注意事項

1.  `text()` 取得的是文字，不是 HTML 子樹。
2.  `attr()` 可能回傳 `None`。
3.  `Selector::parse()` 會失敗，應處理 `Result`。
4.  parser 的錯誤 HTML 復原結果不一定與瀏覽器完全相同。
5.  解析 HTML 不等於安全清理 HTML；若輸出 HTML，仍需正確跳脫或採用合適的
    sanitizer。
6.  若要保留標題之後的完整標記內容，不能只靠
    `text()`。需選擇可保留／序列化節點的解析策略，並設計如何按標題邊界切分內容。
7.  對受控 CMS 內容，Regex 可能簡單而足夠；若 HTML 來源多變，parser
    通常更可靠。

------------------------------------------------------------------------

# 第三章：Closure（閉包）

## 3.1 閉包基本語法

``` rust
let add = |a: i32, b: i32| -> i32 {
    a + b
};
assert_eq!(add(2, 3), 5);
```

`|a, b|` 是參數列表；`-> i32`
是可選的回傳型別註記。型別通常能由使用情境推導，簡單閉包可寫成
`|x| x + 1`。閉包可以捕獲周圍環境中的變數。

常見呼叫 trait：

-   `Fn`：可透過共享參考呼叫。
-   `FnMut`：呼叫時可能修改捕獲環境。
-   `FnOnce`：呼叫時可能消耗捕獲值；所有閉包至少實作 `FnOnce`。
-   `move`：將閉包使用到的捕獲值移入閉包（若型別可
    `Copy`，可能是複製）；不代表所有資料都會深度複製。

## 範例 1：用 map() 將標題轉成檔名

``` rust
fn main() {
    let titles = vec!["首頁".to_string(), "安裝指南".to_string()];
    let filenames: Vec<String> = titles
        .iter()
        .map(|title| format!("{title}.html"))
        .collect();

    for filename in filenames {
        println!("{filename}");
    }
}
```

**解說：** `iter()` 借用元素；`map()` 對每個標題執行閉包；`format!()`
建立新字串；`collect()` 收集成
`Vec<String>`。正式檔名仍應清理非法字元並處理重複檔名。若已有具名函式
`slug_filename`，也可寫 `.map(slug_filename)`。

## 範例 2：用 filter() 過濾 HTML 檔案

``` rust
fn main() {
    let files = vec![
        "index.html".to_string(),
        "style.css".to_string(),
        "sitemap.html".to_string(),
    ];

    let html_files: Vec<&String> = files
        .iter()
        .filter(|name| name.ends_with(".html"))
        .collect();

    for file in html_files {
        println!("{file}");
    }
}
```

**解說：** `filter()` 的閉包回傳 `bool`，決定是否保留元素。因為使用
`iter()`，收集的值是參考；`html_files` 借用 `files`
中的字串。若要消耗原集合，可用 `into_iter()`，但之後不能再使用原集合。

## 範例 3：閉包捕獲 URL 前綴

``` rust
fn main() {
    let base_url = "/manual/";
    let make_url = |filename: &str| format!("{base_url}{filename}");

    println!("{}", make_url("index.html"));
    println!("{}", make_url("install.html"));
}
```

**解說：** 閉包讀取外部
`base_url`，並將它捕獲在環境中。這適合重複使用共同設定。若要讓閉包擁有捕獲的字串，可使用
`move`：

``` rust
let base_url = String::from("/manual/");
let make_url = move |filename: &str| format!("{base_url}{filename}");
```

使用 `move` 後，非 `Copy` 的 `base_url`
通常會被移入閉包，原變數不再能使用。

## 範例 4：用 FnMut 統計產生次數

``` rust
fn main() {
    let mut count = 0_usize;
    let mut next_name = |base: &str| {
        count += 1;
        format!("{base}-{count}.html")
    };

    println!("{}", next_name("page"));
    println!("{}", next_name("page"));
    println!("{}", next_name("page"));
}
```

**解說：** 閉包會修改捕獲的
`count`，因此它需要可變借用，閉包變數也宣告為 `mut`。它實作
`FnMut`。輸出為
`page-1.html`、`page-2.html`、`page-3.html`。這是全域計數示範；正式檔名衝突處理應使用
`HashMap<String, usize>` 對每個基底名稱分別計數。

## 範例 5：把閉包當作函式參數

``` rust
fn transform_titles<F>(titles: &[String], mut transform: F) -> Vec<String>
where
    F: FnMut(&str) -> String,
{
    titles.iter().map(|title| transform(title)).collect()
}

fn main() {
    let titles = vec![" 首頁 ".to_string(), " 安裝 ".to_string()];

    let cleaned = transform_titles(&titles, |title| title.trim().to_string());
    let upper = transform_titles(&titles, |title| title.to_uppercase());

    println!("{cleaned:?}");
    println!("{upper:?}");
}
```

**解說：** `F` 是泛型型別參數，`F: FnMut(&str) -> String`
表示閉包接收字串參考、回傳
`String`，且允許修改捕獲環境。這種泛型參數通常採靜態派發。若需要在執行時保存不同閉包，可考慮
`Box<dyn Fn(&str) -> String>`；若閉包需要修改捕獲狀態，通常要使用
`Box<dyn FnMut(...) -> ...>`，呼叫時也要可變借用。

## 閉包與 Trait Object 的關係

不同閉包通常是不同的匿名型別。如果需要把不同閉包放進同一個集合，可以使用
trait object：

``` rust
let transforms: Vec<Box<dyn Fn(&str) -> String>> = vec![
    Box::new(|text| text.trim().to_string()),
    Box::new(|text| text.to_uppercase()),
];

let input = " rust ";
for transform in &transforms {
    println!("{}", transform(input));
}
```

這裡兩個閉包都不需要修改捕獲環境，所以可用
`dyn Fn(&str) -> String`。若閉包要修改捕獲值，則通常需
`dyn FnMut`，並以可變方式呼叫。

------------------------------------------------------------------------

# 第四章：整合範例------Parser + Closure + Trait Object

本例展示三種技術如何協作：parser 讀取 HTML 標題、閉包產生檔名、trait
object
決定如何輸出。它是架構示範，不是完整分頁器；只列出標題，不會保留標題後的完整
HTML 子樹。

``` rust
use scraper::{Html, Selector};

#[derive(Debug)]
struct HeadingRecord {
    level: String,
    title: String,
    filename: String,
}

trait HeadingSink {
    fn emit(&self, heading: &HeadingRecord);
}

struct ConsoleHeadingSink;

impl HeadingSink for ConsoleHeadingSink {
    fn emit(&self, heading: &HeadingRecord) {
        println!("{} | {} | {}", heading.level, heading.title, heading.filename);
    }
}

fn collect_headings<F>(
    source: &str,
    mut make_filename: F,
) -> Result<Vec<HeadingRecord>, Box<dyn std::error::Error>>
where
    F: FnMut(&str) -> String,
{
    let document = Html::parse_document(source);
    let selector = Selector::parse("h1, h2, h3")?;

    let records = document.select(&selector).map(|element| {
        let level = element.value().name().to_string();
        let title = element.text().collect::<String>().trim().to_string();
        let filename = make_filename(&title);
        HeadingRecord { level, title, filename }
    }).collect();

    Ok(records)
}

fn publish(sink: &dyn HeadingSink, records: &[HeadingRecord]) {
    for record in records {
        sink.emit(record);
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let source = r#"
        <main>
          <h1>Rust 入門</h1>
          <h2>所有權</h2>
          <h3>借用規則</h3>
        </main>
    "#;

    let records = collect_headings(source, |title| {
        let slug: String = title.chars()
            .map(|c| if c.is_whitespace() { '-' } else { c })
            .collect();
        format!("{slug}.html")
    })?;

    publish(&ConsoleHeadingSink, &records);
    Ok(())
}
```

### 程式重點

1.  `HeadingRecord` 用 `struct` 集中儲存解析結果。
2.  `Html::parse_document()` 解析 HTML。
3.  `F: FnMut(&str) -> String` 讓呼叫端提供檔名規則。
4.  `map()` 將元素轉成 `HeadingRecord`。
5.  `HeadingSink` 抽象化輸出方式。
6.  `&dyn HeadingSink` 讓 `publish()` 不必知道輸出器的具體型別。
7.  範例的 slug
    只替換空白，未處理非法字元與重複檔名；正式專案應使用經測試的檔名清理函式及衝突檢查。

------------------------------------------------------------------------

# 第五章：練習題

## 練習一：新增 MarkdownSink

實作 `HeadingSink`，將標題輸出成 Markdown 清單，例如
`- [h1] Rust 入門 -> Rust-入門.html`。

**提示：** 實作 `emit()`，可用 `println!()` 或將內容追加到 `String`。

## 練習二：只處理 main 裡的標題

把 selector 改成 `main h1, main h2, main h3`，確認 `<header>`
中的標題不會列出。

## 練習三：重複檔名加序號

讓檔名產生閉包捕獲 `HashMap<String, usize>`，為重複 slug 加上
`-2`、`-3`。注意不同標題清理後也可能產生相同 slug。

## 練習四：建立驗證器

建立 `HeadingValidator` trait，實作 `HasAtLeastOneHeading` 和
`HasH1`，用 `Vec<Box<dyn HeadingValidator>>` 執行。

## 練習五：比較泛型與 Trait Object

分別用 `fn emit<T: HeadingSink>(sink: &T, ...)` 與
`fn emit(sink: &dyn HeadingSink, ...)`
實作同一功能，比較呼叫方式與設計需求。

------------------------------------------------------------------------

# 第六章：速查表

  ------------------------------------------------------------------------------------------------------
  語法／工具                 用途                       典型寫法
  -------------------------- -------------------------- ------------------------------------------------
  `trait`                    定義共同能力               `trait Render { fn render(&self) -> String; }`

  `impl Trait for Type`      實作 trait                 `impl Render for HtmlPage { ... }`

  `&dyn Trait`               借用 trait object          `fn render(x: &dyn Render)`

  `Box<dyn Trait>`           擁有動態型別物件           `Vec<Box<dyn Render>>`

  `T: Trait`                 泛型約束                   `fn render<T: Render>(x: &T)`

  `Html::parse_document()`   解析 HTML                  `Html::parse_document(source)`

  `Selector::parse()`        解析 CSS selector          `Selector::parse("main h1")?`

  `.select()`                選取節點                   `document.select(&selector)`

  `.text()`                  取得文字節點               `element.text().collect::<String>()`

  `\|x\| expr`               定義閉包                   `let f = \|x\| x + 1;`

  `map()`                    轉換每個元素               `.map(\|x\| transform(x))`

  `filter()`                 過濾元素                   `.filter(\|x\| predicate(x))`

  `Fn`                       不修改捕獲環境的呼叫介面   `F: Fn(&str) -> String`

  `FnMut`                    允許修改捕獲環境           `F: FnMut(&str) -> String`

  `FnOnce`                   可能消耗捕獲值             `F: FnOnce() -> T`

  `move`                     移入捕獲值                 `move \|x\| ...`
  ------------------------------------------------------------------------------------------------------

## 結語

-   **Trait object**：解決不同型別如何透過同一介面使用的問題。
-   **HTML parser**：解決如何依標籤、屬性、文字及節點關係操作 HTML
    的問題。
-   **閉包**：解決如何把可執行邏輯當參數傳遞、重用設定並捕獲環境的問題。

在 HTML 轉換器中，parser 負責讀取結構，閉包提供可替換的轉換規則，trait
object
提供可插拔的輸出或驗證元件。這樣能把工作拆成較小、可測試、容易擴充的模組。
