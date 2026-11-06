import os
import requests
from bs4 import BeautifulSoup

# Discord Webhook URL（GitHub Secretsから自動取得）
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# PCブラウザの通信に偽装する共通ヘッダー
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

MAX_THRESHOLD = 100

def send_discord_notify(site_name, message, target_url):
    """検知時にDiscordへ通知"""
    if not DISCORD_WEBHOOK_URL:
        print(f"[{site_name}] 検知 (Webhook未設定): {message} - {target_url}")
        return

    content = f"🚨 **【{site_name}】直営ECサイトで新着・在庫検知！**\n{message}\n🔗 {target_url}"
    payload = {"content": content}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        print(f"[{site_name}] Discord通知完了")
    except Exception as e:
        print(f"[{site_name}] Discord通知エラー: {e}")

def check_site(name, url, selector=None, no_item_text=None):
    """検索結果ページチェックスクリプト"""
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            print(f"[{name}] ステータス異常: {res.status_code}")
            return

        if "ページが見つかりません" in res.text or "404 Not Found" in res.text:
            print(f"[{name}] 該当なし（エラー文言検知）")
            return

        if no_item_text and no_item_text in res.text:
            print(f"[{name}] 該当なし（0件文言検知）")
            return

        soup = BeautifulSoup(res.text, "html.parser")
        
        if selector:
            items = soup.select(selector)
            count = len(items)
            if 0 < count < MAX_THRESHOLD:
                send_discord_notify(name, f"該当商品要素を {count} 件検知しました！", url)
                return
            else:
                print(f"[{name}] 該当なし (検出数: {count})")
                return

        send_discord_notify(name, "商品ページ・検索結果の変化を検知しました！", url)

    except Exception as e:
        print(f"[{name}] アクセスエラー: {e}")

def check_junsei():
    """Junsei Guitars専用（Gibson一覧ページのHTML本文からTak DC文字列を監視）"""
    url = "https://www.junsei-guitars.com/Gibson/"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            print(f"[Junsei Guitars] ステータス異常: {res.status_code}")
            return

        text_lower = res.text.lower()
        if "tak" in text_lower and ("dc" in text_lower or "matsumoto" in text_lower):
            send_discord_notify("Junsei Guitars", "Gibson一覧ページ内に「Tak Matsumoto / DC」のテキスト記載を検知しました！", url)
        else:
            print("[Junsei Guitars] 該当なし (Tak DC記載なし)")
    except Exception as e:
        print(f"[Junsei Guitars] アクセスエラー: {e}")

def main():
    print("=== 各社ECサイト直監視実行 ===")
    
    # 1. イシバシ楽器
    check_site("イシバシ楽器", "https://store.ishibashi.co.jp/search?q=gibson+tak+matsumoto", ".product-item, .item-list")

    # 2. クロサワ楽器
    check_site("クロサワ楽器", "https://shop.kurosawagakki.com/items/search?q=gibson%20tak%20matsumoto", ".item-card, .item_box")

    # 3. 島村楽器
    check_site("島村楽器", "https://store.shimamura.co.jp/ec/Facet?inputKeywordFacet=gibson%20tak%20matsumoto&kclsf=AND", ".search-result-item, .product-list-item")

    # 4. イケベ楽器
    check_site("イケベ楽器", "https://www.ikebe-gakki.com/Form/Product/ProductList.aspx?shop=0&cat=&bid=ec&dpcnt=20&img=1&sort=07&swrd=gibson+tak+matsumoto&udns=1&fpfl=0&sfl=0&pno=1", ".product_item, .itemList")

    # 5. 三木楽器
    check_site("三木楽器", "https://www.mikigakki.com/shop/goods/search.aspx?search=x&keyword=gibson+tak+matsumoto&search=search", ".goods_list_item, .item_box")

    # 6. 平野楽器ロッキン
    check_site("平野楽器ロッキン", "https://www.rockin.co.jp/shop/category?ProductsSearchModel%5Bgeneral_search%5D=gibson+tak+matsumoto&ProductsSearchModel%5Bonsale_only%5D=1", ".product_item, .item-list")

    # 7. ギタープラネット
    check_site("ギタープラネット", "https://www.guitarplanet.co.jp/?keyword=gibson+tak+matsumoto&x=0&y=0&act=product", ".item_list, .product-box")

    # 8. ワタナベ楽器店
    check_site("ワタナベ楽器店", "https://www.watanabe-mi.com/shopping/search/?s_w=gibson+tak+matsumoto&page=1", ".item_box, .list_item")

    # 9. Junsei Guitars
    check_junsei()

    print("=== 全サイトの監視チェック完了 ===")

if __name__ == "__main__":
    main()
