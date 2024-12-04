# Prosport Calendar telegram Bot for Event Schedule

Register on the website [Procport Calendar](https://dev-level.ru/), subscribe to the events you are interested in.
This repository contains a Telegram bot that retrieves the schedule of events for a user based on the phone numbe.

## Features

- **Event Schedule Retrieval**: Users can send their phone number to the bot, and it will return a list of events they are registered for on the [Prosport Calendar](https://dev-level.ru/) platform.
- **Interactive User Interface**: Supports interactive chats via Telegram.
- **Secure Integration**: Only retrieves data for authenticated phone numbers.

---

## Getting Started

Follow these steps to set up and run the bot:

### Prerequisites

- **Python 3.8+** installed on your system.
- A **Telegram Bot Token** from the [BotFather](https://core.telegram.org/bots#botfather).
- Access to the Dev-Level API or database containing user event registration data.

### Installation

1. Clone the repository:

         git clone https://github.com/your-username/telegram-bot-events.git
         cd telegram-bot-events

2. Install the required Python dependencies:


        pip install -r requirements.txt


3. Configure environment variables:
Create a .env file in the project root with the bot token:

        TOKEN=your-telegram-bot-token

### Usage
1. Start the Bot:
Run the bot with the following command:

        python bot.py

2. Interact with the Bot:

- Find your bot in Telegram using its username.
- Start a conversation and send your phone number.
- The bot will respond with your registered event schedule.
