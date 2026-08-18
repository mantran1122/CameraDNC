# 13. Database Design

## SQLite

### Device

- id
- name
- ip
- port
- username
- last_login

### DownloadHistory

- id
- channel
- start_time
- end_time
- file_path
- status

### EventLog

- id
- level
- message
- created_at

### FavoriteChannel

- id
- device_id
- channel

### Settings

- key
- value

Indexes:
- ip
- created_at
- channel
