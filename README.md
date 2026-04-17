💰 AI Smart Saver - Budget Guardian

A personal budget tracking desktop app built with **Python + Flet**, featuring AI-powered spending insights, multi-user profiles, recurring transaction automation, and a clean dark/light UI.

---

✨ Features

- **Multi-user profiles** - Create multiple profiles with custom emoji avatars; switch anytime
- **Dashboard** - At-a-glance overview of income, expenses, and remaining budget
- **Transactions** - Log income and expenses with category tagging
- **Recurring transactions** - Auto-applied on launch (salary, bills, subscriptions)
- **Budget limits** - Set per-category spending limits and track progress
- **AI Insights** - AI-generated analysis of your spending patterns and saving tips
- **CSV Export** - Export your transaction history for external use
- **Dark / Light theme toggle** - Comfortable viewing any time of day
- **Fully offline** - All data stored locally via SQLite; nothing leaves your device

---

🛠️ Tech Stack

|        Layer | Technology                                          |
|--------------|-----------------------------------------------------|
| UI Framework | [Flet](https://flet.dev/) (Flutter-based Python UI) |
|   Language   |Python 3.10+                                         |
|   Database   |SQLite via custom `database.py`                      |
| AI Insights  |`ai_insights.py` (LLM-powered spending analysis)     |
| Data Export  |CSV via `exports/` folder                            |

---

🚀 Getting Started

Prerequisites

- Python 3.10 or higher
- pip

Installation

```bash
# Clone the repository
git clone https://github.com/salipuranalgine-cmyk/ai-budget-tracker.git
cd ai-budget-tracker

# Install dependencies
pip install flet

# Run the app
python main.py
```

> On first launch, you'll be prompted to create a profile. Enter your name, pick an emoji avatar, and you're good to go.

---

📸 Screenshots

> *(Check the `Guide/` folder for usage screenshots and walkthrough)*

---

🔮 Planned Improvements

- [ ] Charts and spending trend graphs
- [ ] Budget summary notifications
- [ ] Android APK packaging via Flet mobile
- [ ] Improved AI insight prompts with category-level breakdowns

---

👤 Author

**Algine Niño Salipuran**
Computer Engineering Graduate | Python · ML · IoT

- GitHub: [@salipuranalgine-cmyk](https://github.com/salipuranalgine-cmyk)
- LinkedIn: [Algine Niño Salipuran](https://www.linkedin.com/in/algine-ni%C3%B1o-salipuran-8570733a1/)
