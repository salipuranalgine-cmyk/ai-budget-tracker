# 💰 AI Smart Saver — Budget Guardian

A personal budget tracking desktop app built with **Python + Flet**, featuring AI-powered multi-turn chat, a full notification hub, recurring transaction automation, multi-currency support, and a clean dark/light UI.

---

## ✨ Features

### 👤 Multi-User Profiles
- Create multiple profiles with custom emoji avatars
- Each profile gets its own isolated SQLite database
- Auto-resumes the last active profile on launch
- Switch or delete profiles anytime from the profile screen

### 🏠 Dashboard
- At-a-glance overview of balance, total income, and total expenses
- Starting balance support — set your initial cash before tracking begins
- Upcoming recurring bills widget (due within the next few days)
- Quick **+ Income** and **+ Expense** action buttons

### 🧾 Transactions
- Log income and expenses with category tagging, description, and custom date
- Advanced filtering: search by keyword, category, date range, and amount range
- Edit or delete any transaction
- Export full transaction history to CSV

### 🔁 Recurring Transactions
- Set up repeating income or expenses (salary, rent, subscriptions, bills, etc.)
- Frequency options: **daily, weekly, biweekly, monthly, yearly, or custom (N days)**
- All due transactions are **auto-applied on every launch** — no manual action needed
- Enable/disable or edit recurring entries without deleting them

### 📊 Budget Limits
- Set per-category spending limits
- Flexible duration: **monthly** or **custom date range** (start/end date)
- Visual progress bars showing how much of each budget has been used
- Limits auto-refresh against current spending

### 🔔 Notification Hub
- Real-time bell icon with unread count badge in the app bar
- Notification types:
  - 🔴 **Budget Exceeded** — fired when spending hits 100%+ of a category limit
  - 🟠 **Budget Warning** — fired at 80% of a limit
  - 📅 **Bill Due** — overdue, due today, and due within 3 days
  - 🤖 **AI Insight** — urgent alerts surfaced by the AI advisor
- Full management: mark as read, mark all read, delete individual, multi-select delete, clear all
- Notifications persist across sessions and refresh automatically on data changes

### 🤖 AI Insights & Chat
- **Multi-turn conversation** — chat with the AI across multiple messages, not just one-shot
- Persistent **chat session history** saved to SQLite (browse, resume, or delete past sessions)
- Dual-provider support:
  - **Offline (Ollama)** — runs locally with no internet required (llama3.2, qwen2.5, phi3, and more)
  - **Online (Anthropic Claude)** — uses your API key for cloud-based responses
- Configurable provider strategy: **Smart / Online First / Offline First**
- AI automatically generates urgent notifications when it detects budget overruns, low balance, or overdue bills via a structured `[NOTIFY: ...]` tag in its reply
- Fallback keyword scanner for urgent alerts when structured tags aren't present

### 🌍 Multi-Currency Support
Supports 17 currencies with correct symbols and decimal places:

| Code | Currency |
|------|----------|
| PHP | Philippine Peso (₱) |
| USD | US Dollar ($) |
| EUR | Euro (€) |
| GBP | British Pound (£) |
| SGD | Singapore Dollar (S$) |
| AUD | Australian Dollar (A$) |
| CAD | Canadian Dollar (C$) |
| HKD | Hong Kong Dollar (HK$) |
| MYR | Malaysian Ringgit (RM) |
| THB | Thai Baht (฿) |
| VND | Vietnamese Dong (₫) |
| IDR | Indonesian Rupiah (Rp) |
| JPY | Japanese Yen (¥) |
| KRW | South Korean Won (₩) |
| CNY | Chinese Yuan (¥) |
| AED | UAE Dirham |
| SAR | Saudi Riyal |

### ⚙️ Settings
- Switch currency at any time
- Save / update your Anthropic API key (stored locally, masked in the UI)
- Choose AI provider mode (Smart / Online First / Offline First)
- View and clear AI chat storage usage
- Dark / Light theme toggle (available from any screen)

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| UI Framework | [Flet](https://flet.dev/) (Flutter-based Python UI) |
| Language | Python 3.10+ |
| Database | SQLite via custom `database.py` (per-user DBs + shared `users.db`) |
| AI — Offline | [Ollama](https://ollama.com/) local LLM (llama3.2, qwen2.5, phi3, etc.) |
| AI — Online | Anthropic Claude API (`claude-haiku-4-5`) |
| Date Math | `python-dateutil` (relativedelta for monthly/yearly recurrence) |
| Data Export | CSV via `exports/` folder |

---

## 🗄️ Database Schema (per user)

Each user profile has its own SQLite file (`budget_user_<id>.db`) containing:

- `transactions` — all income and expense records
- `budget_limits` — per-category limits with duration and date range
- `recurring_transactions` — repeating transactions with frequency and next-due tracking
- `notifications` — persistent notification inbox
- `chat_sessions` + `chat_messages` — full AI conversation history
- `app_meta` — user preferences (currency, API key, AI mode, starting balance)

---

## 🚀 Getting Started

**Prerequisites**
- Python 3.10 or higher
- pip

**Installation**

```bash
# Clone the repository
git clone https://github.com/salipuranalgine-cmyk/ai-budget-tracker.git
cd ai-budget-tracker

# Install dependencies
pip install flet python-dateutil

# Run the app
python main.py
```

> On first launch, you'll be prompted to create a profile. Enter your name, pick an emoji avatar, and you're good to go. A welcome guide will walk you through the basics.

**Enabling AI (optional)**

*Offline (no internet needed):*
```bash
# Install Ollama from https://ollama.com, then pull a model:
ollama pull llama3.2
```

*Online (any device with internet):*
1. Get an API key from [console.anthropic.com](https://console.anthropic.com)
2. Go to **Settings → AI Setup** in the app and paste your key

---

## 📸 Screenshots

<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_09_58 PM" src="https://github.com/user-attachments/assets/8797b0fa-8ddb-43ac-962a-69694fed207a" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_10_22 PM" src="https://github.com/user-attachments/assets/48c2217e-9b3b-485d-beea-8433ded7e9e2" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_10_42 PM" src="https://github.com/user-attachments/assets/075b431e-b195-4e41-a37e-6c00cb2f1c5d" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_10_48 PM" src="https://github.com/user-attachments/assets/ea295c51-3980-4a0d-b8a1-c962fdf3673d" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_11_28 PM" src="https://github.com/user-attachments/assets/6fb6e458-6036-4fad-a21a-b26e2beb3ca3" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_11_55 PM" src="https://github.com/user-attachments/assets/9c9566bf-668d-47d2-b480-438944a46482" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_12_01 PM" src="https://github.com/user-attachments/assets/e90841ff-e3f2-4d60-b8cc-9873f72c5592" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_12_18 PM" src="https://github.com/user-attachments/assets/75d2172f-f366-4ee0-b07d-4233db4cf1ea" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_23_06 PM" src="https://github.com/user-attachments/assets/364f0b5a-55e5-4e84-87ed-e4d09c0119bb" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_23_36 PM" src="https://github.com/user-attachments/assets/8a579961-3e4a-4eb0-99ac-4414f7174ee4" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_23_49 PM" src="https://github.com/user-attachments/assets/6ad7bd61-9c82-49db-aee8-25f591d9a0ca" />


---

## 🔮 Planned Improvements

- [ ] Charts and spending trend graphs
- [ ] Android APK packaging via Flet mobile

---

## 👤 Author

**Algine Niño Salipuran**  
Computer Engineering Graduate | Python · ML · IoT

- GitHub: [@salipuranalgine-cmyk](https://github.com/salipuranalgine-cmyk)
- LinkedIn: [Algine Niño Salipuran](https://www.linkedin.com/in/algine-ni%C3%B1o-salipuran-8570733a1/)
