import os
import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
STATE_FILE = "watched_items.json"

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
    if not DISCORD_WEBHOOK_URL:
        return

    content = f"🚨 **【{site_name}】Tak Matsumoto モデル新着検知！**\n📌 **{item_title}**\n🔗 {item_url}"
    payload = {"content": content}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    except Exception:
        pass

def check_site_filtered(name, search_url, current_state):
    """一般の楽器店用チェック関数"""
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
        seen_product_ids = set()

        exclude_url_keywords = [
            "login", "cart", "basket", "guide", 
            "faq", "wish", "mypage", "account", 
            "topics", "contact", "info", "policy", "#navi", "shop/category", "favorite"
        ]

        exclude_item_keywords = [
            "ストラップ", "strap", "ケース", "case", "ギグバッグ", "認定証", "ピック", "シールド"
        ]

        for a in all_links:
            href = a["href"]
            netloc = parsed_url.netloc
            
            if href.startswith("/"):
                full_url = f"{parsed_url.scheme}://{netloc}{href}"
            elif href.startswith("http"):
                full_url = href
            else:
                full_url = f"{parsed_url.scheme}://{netloc}/{href}"

            if netloc not in full_url:
                continue

            if "watanabe-mi.com" in netloc:
                if "/shopping/search" in full_url or ("/shopping/list/" in full_url and "/p" not in full_url):
                    continue

            if any(ex in full_url.lower() for ex in exclude_url_keywords):
                continue

            title = a.get_text(strip=True)
            if not title or len(title) <= 3:
                img = a.find("img")
                if img and img.get("alt"):
                    title = img["alt"]
                else:
                    continue

            title_lower = title.lower()

            if any(ex in title_lower for ex in exclude_item_keywords):
                continue

            valid_keywords = ["tak", "matsumoto", "gibson", "epiphone"]
            if not any(kw in title_lower for kw in valid_keywords):
                continue

            numbers = re.findall(r'\d+', full_url)
            prod_id = max(numbers, key=len) if numbers else full_url

            if prod_id in seen_product_ids:
                continue

            seen_product_ids.add(prod_id)
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
        print(f"[{name}] 検出数: {total_count} 件 (うち新規: {new_found_count} 件)")

    except Exception as e:
        print(f"[{name}] アクセスエラー: {e}")

def check_miki_gakki_direct(name, search_url, current_state):
    """三木楽器専用（商品カードクラスを直接狙う安定版）"""
    try:
        parsed_url = urlparse(search_url)
        headers = BASE_HEADERS.copy()
        headers["Referer"] = f"{parsed_url.scheme}://{parsed_url.netloc}/"

        res = requests.get(search_url, headers=headers, timeout=20)
        print(f"[{name}] HTTPステータス: {res.status_code}")

        if res.status_code != 200:
            return

        soup = BeautifulSoup(res.text, "html.parser")
        
        # ご提供いただいたソースにある商品カードのクラスを指定
        item_divs = soup.find_all("div", class_="block-goods-list-d--item")
        
        target_links = []
        seen_ids = set()

        for item in item_divs:
            a_tag = item.find("a", href=lambda h: h and "/shop/g/" in h)
            if not a_tag:
                continue

            href = a_tag["href"]
            if href.startswith("/"):
                full_url = f"https://www.mikigakki.com{href}"
            elif href.startswith("http"):
                full_url = href
            else:
                full_url = f"https://www.mikigakki.com/shop/goods/{href}"

            # title属性から正確な商品名を取得
            title = a_tag.get("title")
            if not title:
                name_div = item.find("div", class_="block-goods-list-d--goods-name")
                title = name_div.get_text(strip=True) if name_div else ""

            if not title or len(title) <= 3:
                continue

            title_lower = title.lower()

            exclude_item_keywords = ["ストラップ", "strap", "ケース", "case", "ギグバッグ", "認定証", "ピック", "シールド"]
            if any(ex in title_lower for ex in exclude_item_keywords):
                continue

            valid_keywords = ["tak", "matsumoto", "gibson", "epiphone"]
            if not any(kw in title_lower for kw in valid_keywords):
                continue

            match = re.search(r'/g/g([A-Za-z0-9\-]+)/', full_url)
            prod_id = match.group(1) if match else full_url

            if prod_id in seen_ids:
                continue
            seen_ids.add(prod_id)
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
        print(f"[{name}] 検出数: {total_count} 件 (うち新規: {new_found_count} 件)")

    except Exception as e:
        print(f"[{name}] アクセスエラー: {e}")

def main():
    print("=== 各社ECサイト監視 サマリー確認 ===")
    
    current_state = load_previous_state()

    check_site_filtered("イシバシ楽器", "https://store.ishibashi.co.jp/search?q=gibson+tak+matsumoto", current_state)
    # check_site_filtered("クロサワ楽器", "https://shop.kurosawagakki.com/items/search?q=gibson%20tak%20matsumoto", current_state)
    check_site_filtered("島村楽器", "https://store.shimamura.co.jp/ec/Facet?inputKeywordFacet=gibson%20tak%20matsumoto&kclsf=AND", current_state)
    check_site_filtered("イケベ楽器", "https://www.ikebe-gakki.com/Form/Product/ProductList.aspx?shop=0&cat=&bid=ec&dpcnt=20&img=1&sort=07&swrd=gibson+tak+matsumoto&udns=1&fpfl=0&sfl=0&pno=1", current_state)
    
    # 三木楽器は直接URLアクセス＆正確なクラス指定で実行
    # check_miki_gakki_direct("三木楽器", "https://www.mikigakki.com/shop/goods/search.aspx?keyword=gibson+tak+matsumoto&search=search&search=x", current_state)
    
    check_site_filtered("平野楽器ロッキン", "https://www.rockin.co.jp/shop/category?ProductsSearchModel%5Bgeneral_search%5D=gibson+tak+matsumoto&ProductsSearchModel%5Bonsale_only%5D=1", current_state)
    check_site_filtered("ギタープラネット", "https://www.guitarplanet.co.jp/?keyword=gibson+tak+matsumoto&x=0&y=0&act=product", current_state)
    check_site_filtered("ワタナベ楽器店", "https://www.watanabe-mi.com/shopping/search/?s_w=gibson+tak+matsumoto&page=1", current_state)

    save_current_state(current_state)

    print("=== チェック完了 ===")

if __name__ == "__main__":
    main()
