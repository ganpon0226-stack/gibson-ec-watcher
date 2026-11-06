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
        return

    content = f"🚨 **【{site_name}】Tak Matsumoto モデル新着検知！**\n📌 **{item_title}**\n🔗 {item_url}"
    payload = {"content": content}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    except Exception:
        pass

def check_site_filtered(name, search_url, current_state):
    """各社ECの検索結果をチェックし、件数のみを簡潔にログ出力する"""
    try:
        parsed_url = urlparse(search_url)
        headers = BASE_HEADERS.copy()
        headers["Referer"] = f"{parsed_url.scheme}://{parsed_url.netloc}/"

        res = requests.get(search_url, headers=headers, timeout=20)
        
        if res.status_code != 200:
            print(f"[{name}] ステータス異常 (HTTP {res.status_code})")
            return

        soup = BeautifulSoup(res.text, "html.parser")
        all_links = soup.find_all("a", href=True)
        
        target_links = []
        seen_urls = set()

        exclude_keywords = [
            "search", "login", "cart", "basket", "category", "guide", 
            "faq", "wish", "mypage", "account", "shopping/list", 
            "topics", "contact", "info", "policy", "#navi", "shop/category"
        ]

        for a in all_links:
            href = a["href"]
            
            if href.startswith("/"):
                full_url = f"{parsed_url.scheme}://{parsed_url.netloc}{href}"
            elif href.startswith("http"):
                full_url = href
            else:
                continue

            if parsed_url.netloc not in full_url:
                continue

            if any(ex in full_url.lower() for ex in exclude_keywords):
                continue

            title = a.get_text(strip=True)
            if not title or len(title) <= 3:
                img = a.find("img")
                if img and img.get("alt"):
                    title = img["alt"]
                else:
                    continue

            title_lower = title.lower()
            valid_keywords = ["tak", "matsumoto", "gibson", "epiphone"]
            if not any(kw in title_lower for kw in valid_keywords):
                continue

            if full_url not in seen_urls:
                seen_urls.add(full_url)
                target_links.append({"title": title, "url": full_url})

        total_count = len(target_links)
        
        known_urls = current_state.get(name, [])
        new_urls = list(known_urls)
        new_found_count = 0

        for p in target_links:
            href = p["url"]
            title = p["title"]

            if href not in known_urls:
                send_discord_notify(name, title, href)
                new_urls.append(href)
                new_found_count += 1

        current_state[name] = new_urls

        # ★ ログには件数（全体数 ＆ 新規数）だけを1行でスッキリ表示
        print(f"[{name}] 検出数: {total_count} 件 (うち新規: {new_found_count} 件)")

    except Exception as e:
        print(f"[{name}] アクセスエラー: {e}")

def main():
    print("=== 各社ECサイト監視 サマリー確認 ===")
    
    current_state = load_previous_state()

    # 各社チェック実行
    check_site_filtered("イシバシ楽器", "https://store.ishibashi.co.jp/search?q=gibson+tak+matsumoto", current_state)
    check_site_filtered("クロサワ楽器", "https://shop.kurosawagakki.com/items/search?q=gibson%20tak%20matsumoto", current_state)
    check_site_filtered("島村楽器", "https://store.shimamura.co.jp/ec/Facet?inputKeywordFacet=gibson%20tak%20matsumoto&kclsf=AND", current_state)
    check_site_filtered("イケベ楽器", "https://www.ikebe-gakki.com/Form/Product/ProductList.aspx?shop=0&cat=&bid=ec&dpcnt=20&img=1&sort=07&swrd=gibson+tak+matsumoto&udns=1&fpfl=0&sfl=0&pno=1", current_state)
    check_site_filtered("三木楽器", "https://www.mikigakki.com/shop/goods/search.aspx?search=x&keyword=gibson+tak+matsumoto&search=search", current_state)
    check_site_filtered("平野楽器ロッキン", "https://www.rockin.co.jp/shop/category?ProductsSearchModel%5Bgeneral_search%5D=gibson+tak+matsumoto&ProductsSearchModel%5Bonsale_only%5D=1", current_state)
    check_site_filtered("ギタープラネット", "https://www.guitarplanet.co.jp/?keyword=gibson+tak+matsumoto&x=0&y=0&act=product", current_state)
    check_site_filtered("ワタナベ楽器店", "https://www.watanabe-mi.com/shopping/search/?s_w=gibson+tak+matsumoto&page=1", current_state)

    save_current_state(current_state)

    print("=== チェック完了 ===")

if __name__ == "__main__":
    main()
