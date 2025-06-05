import os
import json
import re
import sys
from datetime import datetime
import argparse

USER_CACHE = {}

# --- Functions from slack_parser.py --- 
def get_user_name(user_id, users_data):
    """從 users.json 中獲取用戶名，並緩存結果。"""
    if not users_data:
        return user_id
    if user_id in USER_CACHE:
        return USER_CACHE[user_id]
    for user in users_data:
        if user.get('id') == user_id:
            name = user.get('profile', {}).get('real_name', user_id)
            USER_CACHE[user_id] = name
            return name
    USER_CACHE[user_id] = user_id
    return user_id

def format_message(msg, users_data):
    """格式化單條 Slack 訊息。"""
    user_id = msg.get('user', 'Unknown User')
    user_name = get_user_name(user_id, users_data)
    timestamp_str = msg.get('ts', '0')
    try:
        timestamp = datetime.fromtimestamp(float(timestamp_str)).strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        timestamp = 'Invalid Timestamp'
    text = msg.get('text', '')
    files = msg.get('files', [])
    file_texts = []
    for f in files:
        file_texts.append(f"[檔案: {f.get('name', 'N/A')} ({f.get('pretty_type', 'N/A')})]")
    if file_texts:
        text += "\n" + "\n".join(file_texts)
    return f"{timestamp} - {user_name}: {text}"

def parse_slack_export(history_path, output_file):
    """處理 Slack 歷史記錄並輸出到 TXT 檔案。 (Original: process_slack_history from slack_parser.py)"""
    all_messages_by_channel_and_thread = {}
    users_data = []
    users_file_path = os.path.join(history_path, 'users.json')
    if os.path.exists(users_file_path):
        try:
            with open(users_file_path, 'r', encoding='utf-8') as f:
                users_data = json.load(f)
        except Exception as e:
            print(f"讀取 users.json 時發生錯誤: {e}")

    for root_dir, _, files_in_dir in os.walk(history_path):
        # Create a copy of files_in_dir to modify it while iterating
        files_to_process = list(files_in_dir)
        # Files to ignore
        ignore_files = ['users.json', 'integration_logs.json', 'channels.json', 'groups.json', 
                        'dms.json', 'mpims.json', 'canvases.json', 'lists.json',
                        'file_conversations.json', 'huddle_transcripts.json']
        for ignore_file in ignore_files:
            if ignore_file in files_to_process:
                files_to_process.remove(ignore_file)

        channel_name = os.path.basename(root_dir)
        if root_dir == history_path: # Avoid processing root as a channel
            channel_name = "_GeneralRoot_" # Special name for root files, if any
            # Typically, JSON files are in subdirectories (channels)
            # If there are JSONs directly in history_path, they might be special like 'dms.json' etc.
            # which are already handled by ignore_files. This logic is mostly for structure.

        if channel_name not in all_messages_by_channel_and_thread:
            all_messages_by_channel_and_thread[channel_name] = {}

        for file_name in files_to_process:
            if file_name.endswith('.json'):
                file_path = os.path.join(root_dir, file_name)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        daily_messages = json.load(f)
                    for msg in daily_messages:
                        thread_ts = msg.get('thread_ts')
                        ts = msg.get('ts')
                        key = thread_ts if thread_ts else ts
                        if key not in all_messages_by_channel_and_thread[channel_name]:
                            all_messages_by_channel_and_thread[channel_name][key] = []
                        all_messages_by_channel_and_thread[channel_name][key].append(msg)
                except Exception as e:
                    print(f"處理檔案 {file_path} 時發生錯誤: {e}")
    
    with open(output_file, 'w', encoding='utf-8') as out_f:
        # Sort channels by name for consistent output, except for _GeneralRoot_
        sorted_channel_names = sorted([ch for ch in all_messages_by_channel_and_thread if ch != "_GeneralRoot_"])
        if "_GeneralRoot_" in all_messages_by_channel_and_thread and all_messages_by_channel_and_thread["_GeneralRoot_"]:
            # Process _GeneralRoot_ first if it has messages (shouldn't typically happen with Slack exports)
            sorted_channel_names.insert(0, "_GeneralRoot_")
            
        for channel_name in sorted_channel_names:
            threads = all_messages_by_channel_and_thread[channel_name]
            if not threads: continue
            # Do not write channel header if it's the placeholder for root files
            if channel_name != "_GeneralRoot_":
                out_f.write(f"--- 頻道/對話: {channel_name} ---\n\n")
            
            valid_thread_keys = [key for key in threads.keys() if key is not None]
            sorted_thread_keys = sorted(valid_thread_keys)

            for thread_key in sorted_thread_keys:
                messages_in_thread = sorted(threads[thread_key], key=lambda m: float(m.get('ts', 0)))
                parent_message_str = ""
                replies_strs = []
                is_thread_root_processed = False

                for msg_content in messages_in_thread:
                    msg_subtype = msg_content.get('subtype')
                    is_root_of_thread = msg_content.get('thread_ts') and msg_content['thread_ts'] == msg_content.get('ts')
                    is_reply_in_thread = msg_content.get('thread_ts') and msg_content['thread_ts'] != msg_content.get('ts')

                    if is_root_of_thread:
                        parent_message_str = format_message(msg_content, users_data)
                        if msg_content.get('reply_count', 0) > 0:
                            parent_message_str += f" (有 {msg_content.get('reply_count')} 則回覆)"
                        is_thread_root_processed = True
                    elif is_reply_in_thread:
                        replies_strs.append(format_message(msg_content, users_data))
                    elif msg_subtype == 'thread_broadcast':
                        if 'root' in msg_content:
                            root_msg_str = format_message(msg_content['root'], users_data)
                            out_f.write(f"{root_msg_str}\n")
                            broadcast_intro = format_message(msg_content, users_data)
                            out_f.write(f"  └─ Thread Broadcast: {broadcast_intro}\n")
                        else:
                            out_f.write(format_message(msg_content, users_data) + "\n")
                        is_thread_root_processed = True # Mark as processed to avoid double output
                    else: # Normal non-threaded message
                        out_f.write(format_message(msg_content, users_data) + "\n")
                
                if parent_message_str:
                    out_f.write(parent_message_str + "\n")
                    for reply_str in replies_strs:
                        out_f.write(f"  └─ {reply_str}\n")
                elif replies_strs: # Replies without a root in this batch (should be rare)
                     for reply_str in replies_strs:
                        out_f.write(f"  (孤立回覆): {reply_str}\n")
                
                if is_thread_root_processed or replies_strs:
                     out_f.write("\n")
            if channel_name != "_GeneralRoot_": # Add newline after each channel's content
                out_f.write("\n")
    print(f"Slack 歷史記錄已成功轉換到 {output_file}")

# --- Functions from clean_slack_history.py --- 
def remove_sensitive_and_general_plans(input_file_path, output_file_path):
    """(Original: clean_slack_history from clean_slack_history.py)"""
    password_keywords = [
        r'password', r'密碼', r'帳號密碼', r'pwd', r'credentials',
        r'帳密', r'金鑰', r'key', r'secret'
    ]
    plan_keywords = [
        r'今日規劃', r'本日規劃', r'明天規劃', r'明日規劃',
        r'本週計畫', r'本周計畫', r'下週計畫', r'下周計畫',
        r'daily plan', r'weekly plan', r'todo', r'待辦',
        r'工作安排', r'工作計畫', r'日程',
        r'sprint planning', r'衝刺計畫'
    ]
    password_pattern = re.compile(r'|'.join(password_keywords), re.IGNORECASE)
    plan_pattern = re.compile(r'|'.join(plan_keywords), re.IGNORECASE)
    cleaned_lines = []
    try:
        with open(input_file_path, 'r', encoding='utf-8') as infile:
            for line in infile:
                if password_pattern.search(line):
                    continue
                if plan_pattern.search(line):
                    is_direct_message_format = bool(re.match(r'^\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\s-\s', line.strip()))
                    is_thread_reply = line.strip().startswith('└─')
                    is_short_line = len(line.split()) < 10 
                    is_url = line.strip().startswith('<http')
                    if (is_direct_message_format or is_thread_reply) and len(line.split()) < 30:
                        continue
                    elif not (is_direct_message_format or is_thread_reply) and is_short_line and not is_url:
                        continue
                cleaned_lines.append(line)
        with open(output_file_path, 'w', encoding='utf-8') as outfile:
            outfile.writelines(cleaned_lines)
        print(f"Successfully removed sensitive and general plans from '{input_file_path}' and saved to '{output_file_path}'")
    except Exception as e:
        print(f"Error in remove_sensitive_and_general_plans: {e}")
        sys.exit(1)

# --- Functions from process_slack_history.py --- (Note: original was also named clean_slack_history)
def filter_messages_and_channels(input_file_path, output_file_path, channels_to_exclude=None):
    """(Original: clean_slack_history from process_slack_history.py)"""
    if channels_to_exclude is None:
        channels_to_exclude = ["mic-ops"]
    cleaned_lines = []
    skip_current_channel = False
    try:
        with open(input_file_path, 'r', encoding='utf-8') as infile:
            for line in infile:
                line = line.rstrip('\n')
                channel_match = re.match(r"^--- 頻道/對話: (.+) ---$", line)
                if channel_match:
                    current_channel = channel_match.group(1)
                    if current_channel in channels_to_exclude:
                        skip_current_channel = True
                    else:
                        skip_current_channel = False
                        cleaned_lines.append(line)
                    continue
                if skip_current_channel:
                    continue
                if not line.strip():
                    if cleaned_lines and cleaned_lines[-1].strip():
                        cleaned_lines.append("") 
                    continue
                if re.search(r"<@U[A-Z0-9]+> has joined the channel$", line):
                    continue
                if re.search(r"has renamed the channel from .+ to .+", line):
                    continue
                cleaned_lines.append(line)
        while cleaned_lines and not cleaned_lines[-1].strip():
            cleaned_lines.pop()
        with open(output_file_path, 'w', encoding='utf-8') as outfile:
            for i, line_to_write in enumerate(cleaned_lines):
                outfile.write(line_to_write)
                if i < len(cleaned_lines) - 1 or line_to_write.strip():
                    outfile.write('\n')
        print(f"Successfully filtered messages and channels from '{input_file_path}' and saved to '{output_file_path}'")
    except Exception as e:
        print(f"Error in filter_messages_and_channels: {e}")
        sys.exit(1)

# --- Functions from clean_daily_plans.py --- 
def clean_daily_plans(input_file_path, output_file_path):
    header_pattern = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} - .*: \d{4}/\d{2}/\d{2} 規劃$")
    bullet_pattern = re.compile(r"^\s*• ")
    try:
        with open(input_file_path, 'r', encoding='utf-8') as infile, \
             open(output_file_path, 'w', encoding='utf-8') as outfile:
            skipping_bullets = False
            for line in infile:
                stripped_line = line.strip()
                if header_pattern.match(stripped_line):
                    skipping_bullets = True
                    continue 
                if skipping_bullets:
                    if bullet_pattern.match(line):
                        continue
                    else:
                        skipping_bullets = False
                        outfile.write(line)
                else:
                    outfile.write(line)
        print(f"Successfully cleaned daily plans from '{input_file_path}' and saved to '{output_file_path}'")
    except Exception as e:
        print(f"Error in clean_daily_plans: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Process Slack history export.")
    parser.add_argument("slack_export_dir", help="Directory containing the Slack export (JSON files).")
    parser.add_argument("final_output_file", help="Path for the final cleaned output TXT file.")
    parser.add_argument("--excluded_channels", nargs='*', default=["mic-ops"], help="List of channels to exclude (e.g., mic-ops another-channel). Default is 'mic-ops'.")
    args = parser.parse_args()

    # Define intermediate file paths (could be made configurable or use temp files)
    # Ensure the script's directory is used for intermediate files if not specified otherwise
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parsed_output_path = os.path.join(script_dir, "_temp_parsed_output.txt")
    cleaned_passwords_plans_path = os.path.join(script_dir, "_temp_cleaned_passwords_plans.txt")
    filtered_channels_path = os.path.join(script_dir, "_temp_filtered_channels.txt")

    print(f"Starting Slack history processing...")
    print(f"Slack Export Directory: {args.slack_export_dir}")
    print(f"Final Output File: {args.final_output_file}")    
    print(f"Excluded Channels: {args.excluded_channels}")

    # Step 1: Parse Slack export
    print("\nStep 1: Parsing Slack export...")
    if not os.path.isdir(args.slack_export_dir):
        print(f"Error: Slack export directory '{args.slack_export_dir}' not found.")
        sys.exit(1)
    parse_slack_export(args.slack_export_dir, parsed_output_path)

    # Step 2: Remove sensitive info and general plans
    print("\nStep 2: Removing sensitive information and general plans...")
    remove_sensitive_and_general_plans(parsed_output_path, cleaned_passwords_plans_path)

    # Step 3: Filter messages (join/rename) and exclude specified channels
    print("\nStep 3: Filtering messages and excluding channels...")
    filter_messages_and_channels(cleaned_passwords_plans_path, filtered_channels_path, args.excluded_channels)

    # Step 4: Clean daily plans
    print("\nStep 4: Cleaning daily plans...")
    clean_daily_plans(filtered_channels_path, args.final_output_file)

    # Clean up intermediate files
    try:
        os.remove(parsed_output_path)
        os.remove(cleaned_passwords_plans_path)
        os.remove(filtered_channels_path)
        print("\nIntermediate files cleaned up.")
    except OSError as e:
        print(f"\nWarning: Could not remove all intermediate files: {e}")

    print(f"\nProcessing complete. Final output saved to {args.final_output_file}")

if __name__ == '__main__':
    main()
