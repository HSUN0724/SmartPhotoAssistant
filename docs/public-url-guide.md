# 臨時公開網址操作說明

這個方式適合上課展示或短時間測試。每次啟動都會產生一個新的
`https://xxxxx.trycloudflare.com` 網址，手機不必和電腦連接同一個網路。
關閉程式後，該網址就會失效。

## 第一次使用：安裝 cloudflared

1. 開啟 Cloudflare 官方下載頁：
   https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/
2. 下載 Windows 64-bit 的 `cloudflared`。
3. 將檔案重新命名為 `cloudflared.exe`，放進本專案中與 `app.py` 同一層。
4. 在 PowerShell 進入本專案，確認能執行：

```powershell
.\cloudflared.exe --version
```

也可以把 cloudflared 安裝到 Windows PATH；`start_public.ps1` 會自動尋找。

## 每次展示

在能直接看到 `app.py` 的專案資料夾中執行：

```powershell
.\start_public.ps1
```

等畫面顯示類似下列網址：

```text
https://random-words.trycloudflare.com
```

將這個完整 HTTPS 網址傳到手機，用 Safari 或 Chrome 開啟。手機可使用
行動網路或其他 Wi-Fi。

若 PowerShell 阻擋腳本，只針對目前這個視窗暫時允許後再重試：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\start_public.ps1
```

## 展示結束

在執行腳本的 PowerShell 視窗按 `Ctrl+C`。Flask 與臨時網址會一起關閉；
下次啟動時會產生不同網址。

## 注意事項

- 臨時網址只適合展示與測試，不適合正式長期部署。
- 知道網址的人在開啟期間都能使用網站，請只分享給需要測試的人。
- 上傳的照片仍保存在執行 Flask 的這台電腦中。
- 不要把 `.env`、Gemini API Key 或整個專案資料夾分享給他人。
- 若畫面提示連接埠 5000 已使用，先回到舊的 PowerShell 視窗按 `Ctrl+C`。
- 若 cloudflared 顯示 Quick Tunnel 設定檔衝突，暫時重新命名使用者目錄中
  `.cloudflared\config.yml` 或 `.cloudflared\config.yaml` 後再啟動。
