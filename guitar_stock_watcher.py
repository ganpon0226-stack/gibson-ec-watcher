import os
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# Discord Webhook URL（GitHub Secretsから自動取得）
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
STATE_FILE = "watched_items.json"

# 本物のChromeブラウザに偽装するヘッダー
BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0"
}

def load_previous_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_current_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"状態保存エラー: {e}")

def send_discord_notify(site_name, item_title, item_url):
    """新規出品（差分）があった時だけDiscordへ通知"""
    if not DISCORD_WEBHOOK_URL:
        print(f"[{site_name}] 🔥【新規検知】 (Webhook未設定): {item_title} - {item_url}")
        return

    content = f"🚨 **【{site_name}】新着・在庫検知！**\n📌 **{item_title}**\n🔗 {item_url}"
    payload = {"content": content}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        print(f"[{site_name}] Discord通知送信完了: {item_title}")
    except Exception as e:
        print(f"[{site_name}] Discord通知エラー: {e}")

def check_site_broad(name, search_url, current_state):
    """
    CSSセレクタを使わず、ページ内の全<a>タグから
    「商品ページっぽいURL（item, goods, product, detail等）」を自動で広く拾う方式
    """
    try:
        parsed_url = urlparse(search_url)
        headers = BASE_HEADERS.copy()
        headers["Referer"] = f"{parsed_url.scheme}://{parsed_url.netloc}/"

        res = requests.get(search_url, headers=headers, timeout=20)
        
        if res.status_code != 200:
            print(f"[{name}] ステータス異常 (HTTP {res.status_code})")
            return

        soup = BeautifulSoup(res.text, "html.parser")
        
        # ページ内のすべての <a> タグを取得
        all_links = soup.find_all("a", href=True)
        
        product_links = []
        seen_urls = set()

        # ECサイトの「商品詳細」によく含まれるURLキーワード
        product_keywords = ["item", "goods", "product", "detail", "p/", "g/", "shop/g"]
        # 除外したいキーワード（検索、ログイン、カート、カテゴリなど）
        exclude_keywords = ["search", "login", "cart", "basket", "category", "guide", "faq", "wish", "mypage", "account"]

        for a in all_links:
            href = a["href"]
            
            # 絶対パスに変換
            if href.startswith("/"):
                full_url = f"{parsed_url.scheme}://{parsed_url.netloc}{href}"
            elif href.startswith("http"):
                full_url = href
            else:
                continue

            # 自社ドメイン内のリンクに限定
            if parsed_url.netloc not in full_url:
                continue

            # 除外キーワードが含まれる場合はスキップ
            if any(ex in full_url.lower() for ex in exclude_keywords):
                continue

            # 商品らしいキーワードが含まれている、またはURLの階層が深いものを候補にする
            is_product_url = any(kw in full_url.lower() for kw in product_keywords)
            
            if is_product_url and full_url not in seen_urls:
                seen_urls.add(full_url)
                title = a.get_text(strip=True)
                # テキストが短すぎる、または画像のみの場合はalt属性などを補う
                if not title or len(title) <= 2:
                    img = a.find("img")
                    if img and img.get("alt"):
                        title = img["alt"]
                    else:
                        title = "商品詳細ページ"
                
                product_links.append({"title": title, "url": full_url})

        count = len(product_links)
        print(f"[{name}] 検索結果ヒット数（候補リンク）: {count} 件")

        # ログに検出した商品候補をリスト表示
        for p in product_links:
            print(f"  - [{p['title']}] ({p['url']})")

        if count == 0:
            return

        known_urls = current_state.get(name, [])
        new_urls = list(known_urls)

        for p in product_links:
            href = p["url"]
            title = p["title"]

            # 【差分判定】まだDiscordに送っていないURLなら通知
            if href not in known_urls:
                print(f"[{name}] ✨ 新規商品を発見！ Discordへ通知します: {title}")
                send_discord_notify(name, title, href)
                new_urls.append(href)

        current_state[name] = new_urls

    except Exception as e:
        print(f"[{name}] アクセスエラー: {e}")

def main():
    print("=== 各社ECサイト直監視（汎用リンク自動検出版）スタート ===")
    
    current_state = load_previous_state()

    # 1. イシバシ楽器
    check_site_broad("イシバシ楽器", "https://store.ishibashi.co.jp/search?q=gibson+tak+matsumoto", current_state)

    # 2. クロサワ楽器 (403対策としてアクセスを試みる)
    check_site_broad("クロサワ楽器", "https://shop.kurosawagakki.com/items/search?q=gibson%20tak%20matsumoto", current_state)

    # 3. 島村楽器
    check_site_broad("島村楽器", "https://store.shimamura.co.jp/ec/Facet?inputKeywordFacet=gibson%20tak%20matsumoto&kclsf=AND", current_state)

    # 4. イケベ楽器
    check_site_broad("イケベ楽器", "https://www.ikebe-gakki.com/Form/Product/ProductList.aspx?shop=0&cat=&bid=ec&dpcnt=20&img=1&sort=07&swrd=gibson+tak+matsumoto&udns=1&fpfl=0&sfl=0&pno=1", current_state)

    # 5. 三木楽器
    check_site_broad("三木楽器", "https://www.mikigakki.com/shop/goods/search.aspx?search=x&keyword=gibson+tak+matsumoto&search=search", current_state)

    # 6. 平野楽器ロッキン
    check_site_broad("平野楽器ロッキン", "https://www.rockin.co.jp/shop/category?ProductsSearchModel%5Bgeneral_search%5D=gibson+tak+matsumoto&ProductsSearchModel%5Bonsale_only%5D=1", current_state)

    # 7. ギタープラネット
    check_site_broad("ギタープラネット", "https://www.guitarplanet.co.jp/?keyword=gibson+tak+matsumoto&x=0&y=0&act=product", current_state)

    # 8. ワタナベ楽器店
    check_site_broad("ワタナベ楽器店", "https://www.watanabe-mi.com/shopping/search/?s_w=gibson+tak+matsumoto&page=1", current_state)

    save_current_state(current_state)

    print("=== 全サイトの監視チェック完了 ===")

if __name__ == "__main__":
    main()
