import os
import json
import requests
from bs4 import BeautifulSoup

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
STATE_FILE = "watched_items.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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
    """新規出品のみDiscordへ通知"""
    if not DISCORD_WEBHOOK_URL:
        print(f"[{site_name}] 新規検知 (Webhook未設定): {item_title} - {item_url}")
        return

    content = f"🚨 **【{site_name}】新着・在庫検知！**\n📌 **{item_title}**\n🔗 {item_url}"
    payload = {"content": content}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        print(f"[{site_name}] Discord通知完了: {item_title}")
    except Exception as e:
        print(f"[{site_name}] Discord通知エラー: {e}")

def check_site_diff(name, url, link_selector):
    """各社ECの検索結果を巡回し、過去になかった新しい商品URLだけを通知する"""
    print(f"[{name}] チェック中...")
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            print(f"[{name}] ステータス異常: {res.status_code}")
            return

        if "ページが見つかりません" in res.text or "404 Not Found" in res.text:
            print(f"[{name}] エラーページ検出")
            return

        soup = BeautifulSoup(res.text, "html.parser")
        
        # 検索結果から各商品の「商品詳細ページへのリンク」をすべて取得
        item_links = soup.select(link_selector)
        
        current_state = load_previous_state()
        known_urls = current_state.get(name, [])
        
        new_known_urls = list(known_urls)
        found_new = False

        for a_tag in item_links:
            href = a_tag.get("href")
            if not href:
                continue
            
            # 相对パスを絶対パス等に補正（必要に応じて）
            if href.startswith("/"):
                # ドメインを抽出して結合する簡易処理
                from urllib.parse import urlparse
                parsed_url = urlparse(url)
                href = f"{parsed_url.scheme}://{parsed_url.netloc}{href}"
            elif not href.startswith("http"):
                continue

            title = a_tag.get_text(strip=True) or "商品ページ"

            # まだ記録されていないURL（＝本当の新着）の場合のみ通知
            if href not in known_urls:
                print(f"[{name}] 新規商品を発見: {title} ({href})")
                send_discord_notify(name, title, href)
                new_known_urls.append(href)
                found_new = True

        # 状態を更新（次回の比較用に今回のURLリストを保持）
        current_state[name] = new_known_urls
        save_current_state(current_state)

        if not found_new:
            print(f"[{name}] 新着なし（既存商品のみ、または0件）")

    except Exception as e:
        print(f"[{name}] アクセスエラー: {e}")

def check_junsei_diff():
    """Junsei Guitars専用の差分検知"""
    name = "Junsei Guitars"
    url = "https://www.junsei-guitars.com/Gibson/"
    print(f"[{name}] チェック中...")
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            return

        soup = BeautifulSoup(res.text, "html.parser")
        text_lower = res.text.lower()
        
        if "tak" in text_lower and ("dc" in text_lower or "matsumoto" in text_lower):
            # 該当テキストが含まれる<a>タグ等を探す
            for a in soup.find_all("a", href=True):
                if "tak" in a.get_text().lower():
                    href = a["href"]
                    if href.startswith("/"):
                        href = f"https://www.junsei-guitars.com{href}"
                    title = a.get_text(strip=True)
                    
                    current_state = load_previous_state()
                    known_urls = current_state.get(name, [])
                    
                    if href not in known_urls:
                        send_discord_notify(name, title, href)
                        known_urls.append(href)
                        current_state[name] = known_urls
                        save_current_state(current_state)
        else:
            print(f"[{name}] Tak DCの記載なし")

    except Exception as e:
        print(f"[{name}] エラー: {e}")

def main():
    print("=== 各社ECサイト 差分監視スタート ===")
    
    # 1. イシバシ楽器 (商品リンクのCSSセレクタを指定)
    check_site_diff("イシバシ楽器", "https://store.ishibashi.co.jp/search?q=gibson+tak+matsumoto", ".product-item a, .item-list a, .c-product-card__link")

    # 2. クロサワ楽器
    check_site_diff("クロサワ楽器", "https://shop.kurosawagakki.com/items/search?q=gibson%20tak%20matsumoto", ".item-card a, .item_box a")

    # 3. 島村楽器
    check_site_diff("島村楽器", "https://store.shimamura.co.jp/ec/Facet?inputKeywordFacet=gibson%20tak%20matsumoto&kclsf=AND", ".search-result-item a, .product-list-item a")

    # 4. イケベ楽器
    check_site_diff("イケベ楽器", "https://www.ikebe-gakki.com/Form/Product/ProductList.aspx?shop=0&cat=&bid=ec&dpcnt=20&img=1&sort=07&swrd=gibson+tak+matsumoto&udns=1&fpfl=0&sfl=0&pno=1", ".product_item a, .c-product-list__item a")

    # 5. 三木楽器
    check_site_diff("三木楽器", "https://www.mikigakki.com/shop/goods/search.aspx?search=x&keyword=gibson+tak+matsumoto&search=search", ".goods_list_item a, .item_box a")

    # 6. 平野楽器ロッキン
    check_site_diff("平野楽器ロッキン", "https://www.rockin.co.jp/shop/category?ProductsSearchModel%5Bgeneral_search%5D=gibson+tak+matsumoto&ProductsSearchModel%5Bonsale_only%5D=1", ".product_item a, .item-list a")

    # 7. ギタープラネット
    check_site_diff("ギタープラネット", "https://www.guitarplanet.co.jp/?keyword=gibson+tak+matsumoto&x=0&y=0&act=product", ".item_list a, .product-box a")

    # 8. ワタナベ楽器店
    check_site_diff("ワタナベ楽器店", "https://www.watanabe-mi.com/shopping/search/?s_w=gibson+tak+matsumoto&page=1", ".item_box a, .list_item a")

    # 9. Junsei Guitars
    check_junsei_diff()

    print("=== 監視チェック完了 ===")

if __name__ ==0_0 and __name__ == "__main__": # 通常のmain実行
    main()
