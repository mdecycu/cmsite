use regex::Regex;
use serde::Serialize;
use std::collections::HashMap;
use std::env;
use std::error::Error;
use std::fs;
use std::path::{Path, PathBuf};

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

fn strip_tags(input: &str) -> Result<String, Box<dyn Error>> {
    let re = Regex::new(r"(?s)<[^>]*>")?;
    let text = re.replace_all(input, "");

    Ok(text
        .replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", "\"")
        .replace("&#39;", "'"))
}

fn escape_html(input: &str) -> String {
    input
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&#39;")
}

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

    let result = result.trim_end_matches([' ', '.']);

    if result.is_empty() {
        "untitled".to_string()
    } else {
        result.to_string()
    }
}

fn fix_static_paths(html: &str) -> String {
    html.replace("src=\"/images/", "src=\"./../images/")
        .replace("href=\"/downloads/", "href=\"./../downloads/")
        .replace("data=\"/images/", "data=\"./../images/")
        .replace("src=\"/static/", "src=\"./../cms/static/")
        .replace("src=/downloads", "src=./../downloads")
        .replace("pythonpath:['/static/'", "pythonpath:['./../cms/static/'")
        .replace(
            "data-dirname=\"/static\"",
            "data-dirname=\"./../cms/static\"",
        )
}

fn parse_pages(input: &str) -> Result<Vec<Page>, Box<dyn Error>> {
    let heading_re = Regex::new(r"(?is)<h([1-3])\b[^>]*>.*?</h[1-3]\s*>")?;
    let title_re = Regex::new(r"(?is)^<h([1-3])\b[^>]*>(.*?)</h[1-3]\s*>$")?;

    let mut headings: Vec<(usize, usize, usize, String)> = Vec::new();

    for found in heading_re.find_iter(input) {
        let tag = found.as_str();

        let captures = title_re
            .captures(tag)
            .ok_or("無法解析 HTML 標題")?;

        let level: usize = captures[1].parse()?;
        let title = strip_tags(&captures[2])?.trim().to_string();

        headings.push((
            found.start(),
            found.end(),
            level,
            title,
        ));
    }

    if headings.is_empty() {
        return Err(
            "content.htm 中找不到 h1、h2 或 h3 分頁標題".into(),
        );
    }

    let mut title_counts: HashMap<String, usize> = HashMap::new();
    let mut filename_counts: HashMap<String, usize> = HashMap::new();
    let mut pages = Vec::new();

    for i in 0..headings.len() {
        let (_start, end, level, title) = &headings[i];

        let body_end = headings
            .get(i + 1)
            .map(|next| next.0)
            .unwrap_or(input.len());

        let body = input[*end..body_end].to_string();

        let count = title_counts.entry(title.clone()).or_insert(0);
        *count += 1;

        let unique_title =
            if headings.iter().filter(|item| item.3 == *title).count() > 1 {
                format!("{}-{}", title, count)
            } else {
                title.clone()
            };

        let base_name = slug_filename(&unique_title);
        let key = base_name.to_lowercase();
        let filename_count = filename_counts.entry(key).or_insert(0);
        *filename_count += 1;

        let filename = if *filename_count == 1 {
            format!("{}.html", base_name)
        } else {
            format!("{}-{}.html", base_name, filename_count)
        };

        pages.push(Page {
            title: unique_title,
            filename,
            level: *level,
            body,
        });
    }

    Ok(pages)
}

// ------------------------------------------------------------
// HTML 標頭
// 使用 r##"..."##，避免 HTML 的 href="#" 結束字串。
// format! 範本內的 CSS/JavaScript 大括號須使用雙大括號。
// ------------------------------------------------------------

fn html_header(title: &str) -> String {
    format!(
        r##"<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta property="head" content="H1">
<meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
<title>{title}</title>

<link rel="stylesheet" href="./../cms/static/chimper/fonts/icomoon/style.css">
<link rel="stylesheet" href="./../cms/static/chimper/css/bootstrap.min.css">
<link rel="stylesheet" href="./../cms/static/chimper/css/magnific-popup.css">
<link rel="stylesheet" href="./../cms/static/chimper/css/jquery-ui.css">
<link rel="stylesheet" href="./../cms/static/chimper/css/owl.carousel.min.css">
<link rel="stylesheet" href="./../cms/static/chimper/css/owl.theme.default.min.css">
<link rel="stylesheet" href="./../cms/static/chimper/css/bootstrap-datepicker.css">
<link rel="stylesheet" href="./../cms/static/chimper/fonts/flaticon/font/flaticon.css">
<link rel="stylesheet" href="./../cms/static/chimper/css/aos.css">
<link rel="stylesheet" href="./../cms/static/chimper/css/style.css">
<link rel="shortcut icon" href="./../cms/static/favicons.png">

<style type="text/css">
.site-section {{ background-color: #FFFF; padding: 40px 40px; }}
body > div > div.dropdown.open {{ display: block; }}
img.add_border {{ border: 3px solid blue; }}

.page-navigation {{
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
    width: 100%;
    box-sizing: border-box;
    gap: 20px;
    margin: 24px 0;
    padding: 12px 0;
    border-top: 1px solid #ddd;
    border-bottom: 1px solid #ddd;
}}

.page-navigation .previous {{
    flex: 1 1 50%;
    min-width: 0;
    margin-right: auto;
    text-align: left;
}}

.page-navigation .next {{
    flex: 1 1 50%;
    min-width: 0;
    margin-left: auto;
    text-align: right;
}}

.page-navigation a {{
    display: inline-block;
    text-decoration: none;
    overflow-wrap: anywhere;
}}

.page-navigation a:hover {{
    text-decoration: underline;
}}
</style>

<script src="../cms/static/chimper/js/jquery-3.3.1.min.js"></script>
<link rel="stylesheet" href="./../cms/static/tipuesearch/css/normalize.min.css">
<script src="./../cms/static/tipuesearch/tipuesearch_set.js"></script>
<script src="tipuesearch_content.js"></script>
<link rel="stylesheet" href="./../cms/static/tipuesearch/css/tipuesearch.css">
<script src="./../cms/static/tipuesearch/tipuesearch.js"></script>

<script>
function doSearch() {{
    if (window.jQuery && jQuery.fn.tipuesearch) {{
        jQuery('#tipue_search_input').tipuesearch({{
            newWindow: true,
            minimumLength: 2,
            wholeWords: false
        }});
    }}
}}

if (window.jQuery) {{
    jQuery(document).ready(doSearch);
}}
</script>

<script type="text/javascript" src="./../cms/static/syntaxhighlighter/shCore.js"></script>
<script type="text/javascript" src="./../cms/static/syntaxhighlighter/shBrushBash.js"></script>
<script type="text/javascript" src="./../cms/static/syntaxhighlighter/shBrushDiff.js"></script>
<script type="text/javascript" src="./../cms/static/syntaxhighlighter/shBrushJScript.js"></script>
<script type="text/javascript" src="./../cms/static/syntaxhighlighter/shBrushJava.js"></script>
<script type="text/javascript" src="./../cms/static/syntaxhighlighter/shBrushPython.js"></script>
<script type="text/javascript" src="./../cms/static/syntaxhighlighter/shBrushSql.js"></script>
<script type="text/javascript" src="./../cms/static/syntaxhighlighter/shBrushHaxe.js"></script>
<script type="text/javascript" src="./../cms/static/syntaxhighlighter/shBrushXml.js"></script>
<script type="text/javascript" src="./../cms/static/syntaxhighlighter/shBrushPhp.js"></script>
<script type="text/javascript" src="./../cms/static/syntaxhighlighter/shBrushPowerShell.js"></script>
<script type="text/javascript" src="./../cms/static/syntaxhighlighter/shBrushLua.js"></script>
<script type="text/javascript" src="./../cms/static/syntaxhighlighter/shBrushMojo.js"></script>
<script type="text/javascript" src="./../cms/static/syntaxhighlighter/shBrushWbt.js"></script>
<script type="text/javascript" src="./../cms/static/syntaxhighlighter/shBrushCpp.js"></script>
<script type="text/javascript" src="./../cms/static/syntaxhighlighter/shBrushCss.js"></script>
<script type="text/javascript" src="./../cms/static/syntaxhighlighter/shBrushCSharp.js"></script>
<script type="text/javascript" src="./../cms/static/syntaxhighlighter/shBrushDart.js"></script>
<script type="text/javascript" src="./../cms/static/syntaxhighlighter/shBrushRust.js"></script>
<link type="text/css" rel="stylesheet" href="./../cms/static/syntaxhighlighter/css/shCoreDefault.css">
<script>if (window.SyntaxHighlighter) SyntaxHighlighter.all();</script>
</head>

<body>
<div class="container">
<div class="site-wrap">

<div class="site-mobile-menu">
  <div class="site-mobile-menu-header">
    <div class="site-mobile-menu-close mt-3">
      <span class="icon-close2 js-menu-toggle"></span>
    </div>
  </div>
  <div class="site-mobile-menu-body"></div>
</div>

<header class="site-navbar py-4 bg-white" role="banner">
  <div class="container">
    <div class="row align-items-center">
      <h1>Dialog</h1>

      <div class="pl-4">
        <form action="#" onsubmit="return false;">
          <input type="text"
                 placeholder="Search"
                 name="q"
                 id="tipue_search_input"
                 pattern=".{{2,}}"
                 title="At least 2 characters">
        </form>
      </div>

      <div class="col-12 col-md-10 d-none d-xl-block">
        <nav class="site-navigation position-relative text-right" role="navigation">
          <!-- NAVIGATION_MENU_INSERTED_BY_CONVERTER -->
        </nav>
      </div>

      <div class="d-inline-block d-xl-none ml-md-0 mr-auto py-3"
           style="position: relative; top: 3px;">
        <a href="#" class="site-menu-toggle js-menu-toggle text-black">
          <span class="icon-menu h3"></span>
        </a>
      </div>
    </div>
  </div>
</header>

<div id="tipue_search_content">
"##,
        title = escape_html(title)
    )
}

// ------------------------------------------------------------
// 建立 h1 / h2 / h3 樹狀選單
// ------------------------------------------------------------

fn insert_nav_node(
    nodes: &mut Vec<NavNode>,
    page_index: usize,
    depth: usize,
) {
    if depth <= 1 || nodes.is_empty() {
        nodes.push(NavNode {
            page_index,
            children: Vec::new(),
        });
        return;
    }

    if let Some(last_node) = nodes.last_mut() {
        insert_nav_node(
            &mut last_node.children,
            page_index,
            depth - 1,
        );
    }
}

fn build_navigation_tree(pages: &[Page]) -> Vec<NavNode> {
    let mut roots: Vec<NavNode> = Vec::new();

    for (index, page) in pages.iter().enumerate() {
        let level = page.level.clamp(1, 3);

        insert_nav_node(
            &mut roots,
            index,
            level,
        );
    }

    roots
}

fn render_nav_nodes(
    nodes: &[NavNode],
    pages: &[Page],
    output: &mut String,
) {
    for node in nodes {
        let page = &pages[node.page_index];

        if node.children.is_empty() {
            output.push_str("<li>");
        } else {
            output.push_str("<li class=\"has-children\">");
        }

        output.push_str(&format!(
            "<a href=\"{}\">{}</a>",
            escape_html(&page.filename),
            escape_html(&page.title)
        ));

        if !node.children.is_empty() {
            output.push_str("<ul class=\"dropdown\">\n");

            render_nav_nodes(
                &node.children,
                pages,
                output,
            );

            output.push_str("</ul>\n");
        }

        output.push_str("</li>\n");
    }
}

fn navigation_links(pages: &[Page]) -> String {
    let mut output = String::from(
        r#"<ul class="site-menu js-clone-nav mr-auto d-none d-lg-block">
<li class="active has-children">
<a href="index.html">Home</a>
<ul class="dropdown">
<li><a href="sitemap.html">SMap</a></li>
</ul>
</li>
"#,
    );

    let tree = build_navigation_tree(pages);

    render_nav_nodes(
        &tree,
        pages,
        &mut output,
    );

    output.push_str("</ul>\n");
    output
}

// ------------------------------------------------------------
// HTML 頁尾
// ------------------------------------------------------------

fn html_footer() -> &'static str {
    r#"
</div><!-- /tipue_search_content -->

<div class="container">
  <div class="row pt-3 mx-auto">
    <p>
      Copyright &copy;<script>document.write(new Date().getFullYear());</script>
      All rights reserved |
      <i class="icon-heart" aria-hidden="true"></i>
      by <a href="https://colorlib.com" target="_blank">Colorlib</a>
    </p>
  </div>
</div>

</div><!-- /site-wrap -->

<script src="../cms/static/chimper/js/jquery-migrate-3.0.1.min.js"></script>
<script src="../cms/static/chimper/js/jquery-ui.js"></script>
<script src="../cms/static/chimper/js/popper.min.js"></script>
<script src="../cms/static/chimper/js/bootstrap.min.js"></script>
<script src="../cms/static/chimper/js/owl.carousel.min.js"></script>
<script src="../cms/static/chimper/js/jquery.stellar.min.js"></script>
<script src="../cms/static/chimper/js/jquery.countdown.min.js"></script>
<script src="../cms/static/chimper/js/jquery.magnific-popup.min.js"></script>
<script src="../cms/static/chimper/js/bootstrap-datepicker.min.js"></script>
<script src="../cms/static/chimper/js/aos.js"></script>
<script src="../cms/static/chimper/js/main.js"></script>
</body>
</html>
"#
}

// ------------------------------------------------------------
// Previous / Next 導覽列
// Previous 靠左，Next 靠右。
// 上方與下方共用同一個函式。
// ------------------------------------------------------------

fn render_previous_next(
    index: usize,
    pages: &[Page],
) -> String {
    let mut output = String::from(
        "<nav class=\"page-navigation\" aria-label=\"Page navigation\">\n",
    );

    if index > 0 {
        let previous = &pages[index - 1];

        output.push_str(&format!(
            "<div class=\"previous\">\
             &lt;&lt; <a href=\"{}\">Previous: {}</a>\
             </div>\n",
            escape_html(&previous.filename),
            escape_html(&previous.title)
        ));
    } else {
        output.push_str("<div class=\"previous\"></div>\n");
    }

    if index + 1 < pages.len() {
        let next = &pages[index + 1];

        output.push_str(&format!(
            "<div class=\"next\">\
             <a href=\"{}\">Next: {}</a> &gt;&gt;\
             </div>\n",
            escape_html(&next.filename),
            escape_html(&next.title)
        ));
    } else {
        output.push_str("<div class=\"next\"></div>\n");
    }

    output.push_str("</nav>\n");
    output
}

// ------------------------------------------------------------
// 產生單一分頁
// ------------------------------------------------------------

fn render_page(
    index: usize,
    pages: &[Page],
) -> String {
    let page = &pages[index];

    let mut output = html_header(&page.title);

    output = output.replace(
        "<!-- NAVIGATION_MENU_INSERTED_BY_CONVERTER -->",
        &navigation_links(pages),
    );

    output.push_str(&format!(
        "<h1>{}</h1>\n",
        escape_html(&page.title)
    ));

    // 頁面上方：Previous 靠左，Next 靠右。
    output.push_str(&render_previous_next(index, pages));

    // 原始 HTML 內容。
    output.push_str(&fix_static_paths(&page.body));

    // 頁面下方：同樣使用左右分開的導覽列。
    output.push_str(&render_previous_next(index, pages));

    output.push_str(html_footer());

    output
}

// index.html 與第一個分頁使用完全相同的頁面內容。
fn render_index(pages: &[Page]) -> String {
    render_page(0, pages)
}

// ------------------------------------------------------------
// 網站地圖
// ------------------------------------------------------------

fn render_sitemap(pages: &[Page]) -> String {
    let mut output = html_header("網站地圖");

    output = output.replace(
        "<!-- NAVIGATION_MENU_INSERTED_BY_CONVERTER -->",
        &navigation_links(pages),
    );

    output.push_str("<h1>網站地圖</h1>\n<ul>\n");

    for page in pages {
        output.push_str(&format!(
            "<li class=\"level-{}\"><a href=\"{}\">{}</a></li>\n",
            page.level,
            escape_html(&page.filename),
            escape_html(&page.title)
        ));
    }

    output.push_str("</ul>\n");
    output.push_str(html_footer());

    output
}

// ------------------------------------------------------------
// 轉換與輸出
// ------------------------------------------------------------

fn generate(
    input_path: &Path,
    output_dir: &Path,
) -> Result<(), Box<dyn Error>> {
    println!("讀取：{}", input_path.display());

    let input = fs::read_to_string(input_path)?;
    let pages = parse_pages(&input)?;

    if pages.is_empty() {
        return Err("沒有可產生的分頁".into());
    }

    fs::create_dir_all(output_dir)?;

    fs::write(
        output_dir.join("index.html"),
        render_index(&pages),
    )?;

    fs::write(
        output_dir.join("sitemap.html"),
        render_sitemap(&pages),
    )?;

    let mut search_pages: Vec<SearchPage> = Vec::new();

    for (index, page) in pages.iter().enumerate() {
        let output_path = output_dir.join(&page.filename);

        fs::write(
            &output_path,
            render_page(index, &pages),
        )?;

        search_pages.push(SearchPage {
            title: page.title.clone(),
            text: strip_tags(&page.body)?,
            tags: String::new(),
            url: page.filename.clone(),
        });

        println!("產生：{}", output_path.display());
    }

    let search_json = serde_json::to_string(&search_pages)?;

    let search_js = format!(
        "var tipuesearch = {{\"pages\": {}}};\n",
        search_json
    );

    fs::write(
        output_dir.join("tipuesearch_content.js"),
        search_js,
    )?;

    println!("\n轉檔完成！");
    println!("分頁數量：{}", pages.len());
    println!("輸出目錄：{}", output_dir.display());

    Ok(())
}

// ------------------------------------------------------------
// 主程式
// ------------------------------------------------------------

fn main() {
    let args: Vec<String> = env::args().collect();

    if args.iter().any(|arg| arg == "--help" || arg == "-h") {
        println!("CMS 靜態 HTML 轉換工具");
        println!("用法：");
        println!("  convert.exe");
        println!("  convert.exe <輸入檔案> <輸出目錄>");
        return;
    }

    let input = args
        .get(1)
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            PathBuf::from("config").join("content.htm")
        });

    let output = args
        .get(2)
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("content"));

    if let Err(err) = generate(&input, &output) {
        eprintln!("轉檔失敗：{err}");
        std::process::exit(1);
    }
}