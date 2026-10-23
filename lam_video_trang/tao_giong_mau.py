import asyncio, os, sys
import edge_tts
sys.stdout.reconfigure(encoding="utf-8")
D = os.path.dirname(os.path.abspath(__file__))

BAI = {
    "meo_noi_chay": ("vi-VN-HoaiMyNeural",
        "Nồi bị cháy đen? Khoan vứt đi! Chỉ với ba thứ có sẵn trong bếp, nồi sẽ sáng bóng như mới. "
        "Bước một: đổ giấm ăn ngập vết cháy, đun sôi khoảng năm phút. "
        "Bước hai: tắt bếp, rắc hai thìa baking soda. Hỗn hợp sủi bọt mạnh, đó là lúc vết cháy bắt đầu bong ra. "
        "Bước ba: để nguội, dùng miếng bọt biển chà nhẹ theo vòng tròn. Vết cháy cứng đầu thì làm lại thêm một lần. "
        "Lưu ý: nồi chống dính tuyệt đối không dùng miếng chà kim loại, sẽ làm tróc lớp chống dính. "
        "Mẹo nhỏ: chà thêm nửa quả chanh, nồi vừa thơm vừa sáng hơn. "
        "Lưu lại ngay để dùng khi cần, và theo dõi Trang để xem thêm mẹo hay mỗi ngày nhé!"),
    "su_that_bach_tuoc": ("vi-VN-NamMinhNeural",
        "Bạch tuộc có ba trái tim và máu màu xanh! "
        "Hai trái tim bơm máu qua mang, trái tim còn lại bơm máu đi khắp cơ thể. "
        "Khi bạch tuộc bơi, trái tim thứ ba ngừng đập. Vì vậy chúng thích bò hơn bơi, vì bơi rất mệt. "
        "Máu của chúng màu xanh lam vì chứa đồng thay vì sắt như máu người, giúp sống được ở vùng nước lạnh, ít ô xy. "
        "Chưa hết, khoảng hai phần ba tế bào thần kinh của bạch tuộc nằm ở tám xúc tu, nên mỗi xúc tu gần như tự suy nghĩ được. "
        "Chúng còn đổi màu da trong chưa đầy một giây để ngụy trang. "
        "Bạn biết sự thật thú vị nào về động vật? Bình luận cho mình biết, và theo dõi Trang để xem thêm nhé!"),
}


async def main():
    import json
    for name, (voice, text) in BAI.items():
        out = os.path.join(D, name + ".mp3")
        items = []
        with open(out, "wb") as f:     # luu kem moc tung tu -> <ten>.timing.json: phu de dung chu kich ban
            async for ch in edge_tts.Communicate(text, voice, rate="+8%", boundary="WordBoundary").stream():
                if ch["type"] == "audio":
                    f.write(ch["data"])
                elif ch["type"] == "WordBoundary":
                    s = ch["offset"] / 1e7
                    items.append({"text": ch["text"], "start": round(s, 3), "end": round(s + ch["duration"] / 1e7, 3)})
        total = items[-1]["end"] + 0.5 if items else 0
        with open(os.path.join(D, name + ".timing.json"), "w", encoding="utf-8") as f:
            json.dump({"total": total, "items": items}, f, ensure_ascii=False)
        with open(os.path.join(D, name + ".txt"), "w", encoding="utf-8") as f:
            f.write(text)
        print("OK", name)

asyncio.run(main())
