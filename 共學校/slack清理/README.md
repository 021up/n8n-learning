# Slack 歷史記錄處理工具

本工具 (`main.py`) 用於處理 Slack 的 JSON 格式歷史記錄匯出檔案，將其轉換為乾淨的文字檔案，並進行多項清理步驟。

## 功能

1.  **解析 Slack 匯出**：讀取 Slack 匯出資料夾中的 JSON 檔案，提取訊息內容、使用者名稱和時間戳。
2.  **移除敏感資訊**：自動移除包含密碼相關關鍵字的訊息。
3.  **移除一般工作計劃**：移除與一般工作計劃相關的討論內容。
4.  **過濾訊息**：移除頻道加入/離開/重命名等系統訊息。
5.  **排除特定頻道**：允許使用者指定要從處理中排除的頻道。
6.  **清理每日計劃**：移除格式如 "YYYY/MM/DD 規劃" 的重複性每日計劃條目及其項目符號內容。
7.  **輸出整合檔案**：將所有處理後的內容按時間順序合併到一個最終的文字檔案中。

## 前提條件

*   Python 3.x

## 設定

1.  將您的 Slack 匯出資料夾（通常名為 `slack-history` 或類似名稱，包含各個頻道的 JSON 檔案和 `users.json`、`channels.json` 等）放置在與 `slack_processing_tool` 資料夾同層的目錄下。

    建議的資料夾結構如下：

    ```
    your_project_directory/
    ├── slack-history/          <-- 您的 Slack 匯出資料夾
    │   ├── channel1/
    │   │   └── YYYY-MM-DD.json
    │   ├── channel2/
    │   │   └── YYYY-MM-DD.json
    │   ├── users.json
    │   ├── channels.json
    │   └── ...
    └── slack_processing_tool/  <-- 本工具資料夾
        ├── main.py
        └── README.md
    ```

## 使用方法

在終端機中，導航到 `slack_processing_tool` 資料夾，然後執行以下命令：

```bash
python3 main.py <slack_export_directory> <output_file_name> [--exclude_channels CHANNEL1 CHANNEL2 ...]
```

**參數說明：**

*   `<slack_export_directory>`：Slack 匯出資料夾的路徑。相對於 `main.py` 的位置，如果按照建議的結構，這裡應該是 `../slack-history`。
*   `<output_file_name>`：最終清理後的文字檔案名稱。例如：`cleaned_history.txt`。此檔案將保存在 `slack_processing_tool` 資料夾內。
*   `--exclude_channels` (可選)：一個或多個要排除的頻道名稱，用空格分隔。例如：`mic-ops general`。

**範例：**

假設您的 Slack 匯出資料夾位於 `../slack-history`，您希望將輸出檔案命名為 `final_cleaned_slack_data.txt`，並排除 `mic-ops` 和 `random` 頻道：

```bash
cd /Users/mic/Documents/4trae/slack-exp/slack_processing_tool
python3 main.py ../slack-history final_cleaned_slack_data.txt --exclude_channels mic-ops random
```

## 輸出

腳本執行完畢後，會在 `slack_processing_tool` 資料夾內生成一個名為 `<output_file_name>` 的文字檔案，其中包含所有已處理和清理過的 Slack 訊息。

## 注意事項

*   腳本在執行過程中會產生一些暫存檔案 (例如 `_temp_parsed.txt`, `_temp_cleaned_passwords.txt` 等)，這些檔案在處理完成後會自動刪除。
*   請確保提供的 Slack 匯出資料夾路徑正確，且資料夾內包含有效的 Slack 匯出 JSON 檔案。
