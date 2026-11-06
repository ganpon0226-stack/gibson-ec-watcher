import os
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# Discord Webhook URL（GitHub Secretsから自動取得）
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
STATE_FILE = "watched_items.json"

# 本物のChromeブラウザに限りなく偽装した拡張ヘッダー
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
    """前回検知した商品のURLリストを読み込む"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_current_state(state):
    """現在の状態を保存する"""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"状態保存エラー: {e}")

def send_discord_notify(site_name, item_title, item_url):
    """新着（差分）があった時だけDiscordへ通知"""
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

def check_site(name, search_url, item_selector, current_state):
    """拡張ヘッダーを用いて各社ECをチェック"""
    try:
        # 各サイトのドメインに応じたRefererを設定して弾かれにくくする
        parsed_url = urlparse(search_url)
        headers = BASE_HEADERS.copy()
        headers["Referer"] = f"{parsed_url.scheme}://{parsed_url.netloc}/"

        res = requests.get(search_url, headers=headers, timeout=20)
        
        if res.status_code != 200:
            print(f"[{name}] ステータス異常 (HTTP {res.status_code})")
            return

        if "ページが見つかりません" in res.text or "404 Not Found" in res.text:
            print(f"[{name}] 検索結果ヒット数: 0 件 (エラーページ)")
            return

        soup = BeautifulSoup(res.text, "html.parser")
        items = soup.select(item_selector)
        count = len(items)
        print(f"[{name}] 検索結果ヒット数: {count} 件")

        if count == 0:
            return

        known_urls = current_state.get(name, [])
        new_urls = list(known_urls)

        for a_tag in items:
            if a_tag.name != 'a':
                a_tag = a_tag.find('a')
            
            if not a_tag or not a_tag.get("href"):
                continue

            href = a_tag["href"]
            
            if href.startswith("/"):
                href = f"{parsed_url.scheme}://{parsed_url.netloc}{href}"
            elif not href.startswith("http"):
                continue

            title = a_tag.get_text(strip=True) or "商品ページ"

            if href not in known_urls:
                print(f"[{name}] ✨ 新規商品を発見！ Discordへ通知します: {title}")
                send_discord_notify(name, title, href)
                new_urls.append(href)

        current_state[name] = new_urls

    except Exception as e:
        print(f"[{name}] アクセスエラー: {e}")

def check_junsei(current_state):
    """Junsei Guitars専用（拡張ヘッダー版）"""
    name = "Junsei Guitars"
    url = "https://www.junsei-guitars.com/Gibson/"
    try:
        headers = BASE_HEADERS.copy()
        headers["Referer"] = "https://www.junsei-guitars.com/"

        res = requests.get(url, headers=headers, timeout=20)
        if res.status_code != 200:
            print(f"[{name}] ステータス異常 (HTTP {res.status_code})")
            return

        text_lower = res.text.lower()
        if "tak" in text_lower and ("dc" in text_lower or "matsumoto" in text_lower):
            print(f"[{name}] キーワード検知: 「Tak / DC」あり！")
            
            soup = BeautifulSoup(res.text, "html.parser")
            known_urls = current_state.get(name, [])
            new_urls = list(known_urls)

            for a in soup.find_all("a", href=True):
                if "tak" in a.get_text().lower():
                    href = a["href"]
                    if href.startswith("/"):
                        href = f"https://www.junsei-guitars.com{href}"
                    title = a.get_text(strip=True)
                    
                    if href not in known_urls:
                        print(f"[{name}] ✨ 新規掲載を発見！ Discordへ通知します: {title}")
                        send_discord_notify(name, title, href)
                        new_urls.append(href)

            current_state[name] = new_urls
        else:
            print(f"[{name}] キーワード検知: なし (0件)")
    except Exception as e:
        print(f"[{name}] アクセスエラー: {e}")

def main():
    print("=== 各社ECサイト直監視（拡張ヘッダー版）スタート ===")
    
    current_state = load_previous_state()

    # 1. イシバシ楽器
    check_site("イシバシ楽器", "https://store.ishibashi.co.jp/search?q=gibson+tak+matsumoto", ".product-item a, .item-list a", current_state)

    # 2. クロサワ楽器
    check_site("クロサワ楽器", "https://shop.kurosawagakki.com/items/search?q=gibson%20tak%20matsumoto", ".item-card a, .item_box a", current_state)

    # 3. 島村楽器
    check_site("島村楽器", "https://store.shimamura.co.jp/ec/Facet?inputKeywordFacet=gibson%20tak%20matsumoto&kclsf=AND", ".search-result-item a, .product-list-item a", current_state)

    # 4. イケベ楽器
    check_site("イケベ楽器", "https://www.ikebe-gakki.com/Form/Product/ProductList.aspx?shop=0&cat=&bid=ec&dpcnt=20&img=1&sort=07&swrd=gibson+tak+matsumoto&udns=1&fpfl=0&sfl=0&pno=1", ".product_list_detail .product_item a, .c-product-list__item a", current_state)

    # 5. 三木楽器
    check_site("三木楽器", "https://www.mikigakki.com/shop/goods/search.aspx?search=x&keyword=gibson+tak+matsumoto&search=search", ".goods_list_item a, .item_box a", current_state)

    # 6. 平野楽器ロッキン
    check_site("平野楽器ロッキン", "https://www.rockin.co.jp/shop/category?ProductsSearchModel%5Bgeneral_search%5D=gibson+tak+matsumoto&ProductsSearchModel%5Bonsale_only%5D=1", ".product_item a, .item-list a", current_state)

    # 7. ギタープラネット
    check_site("ギタープラネット", "https://www.guitarplanet.co.jp/?keyword=gibson+tak+matsumoto&x=0&y=0&act=product", ".item_list a, .product-box a", current_state)

    # 8. ワタナベ楽器店
    check_site("ワタナベ楽器店", "https://www.watanabe-mi.com/shopping/search/?s_w=gibson+tak+matsumoto&page=1", ".item_box a, .list_item a", current_state)

    # 9. Junsei Guitars
    check_junsei(current_state)

    save_current_state(current_state)

    print("=== 全サイトの監視チェック完了 ===")

if __name__ == "__main__":
    main()
