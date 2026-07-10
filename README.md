# Zenith Bank - Vulnerable Web Application

## Overview
Zenith Bank is a purposefully vulnerable web application built to simulate an online banking platform. It is designed exclusively for cybersecurity professionals, students, and enthusiasts to practice penetration testing and vulnerability assessment in a safe, controlled environment.

## Features
The application includes a variety of standard banking features, providing a broad attack surface for security testing:
*   **User Authentication:** Workflows for user registration and account login (`register.html`, `login.html`).
*   **User Dashboard & Profile:** Centralized interfaces for account management and viewing profile details (`dashboard.html`, `profile.html`).
*   **Financial Transactions:** Functionalities for processing fund transfers and bill payments (`transfer.html`, `bill_payments.html`).
*   **Virtual Cards & Loans:** Modules allowing users to request loans and manage virtual banking cards (`loan.html`, `virtual_cards.html`).
*   **Account History:** Systems for tracking user activities, logs, and past transactions (`history.html`).
*   **Admin Privileges:** Administrative backend panels for monitoring transactions and managing user details (`admin.html`, `admin_users.html`, `admin_user_details.html`, `admin_transactions.html`).

## Technology Stack
*   **Backend:** Built in Python, utilizing the Flask web framework (`app.py`, `config.py`).
*   **Database:** Structured using ORM models, with Alembic configured for database migrations (`models.py`, `alembic.ini`, `migrations/`).
*   **Frontend:** Custom HTML templates styled with CSS and JavaScript (`templates/`, `static/css/`, `static/js/`).
*   **Deployment:** Fully containerized environment for isolated deployment (`Dockerfile`, `docker-compose.yml`).

## Installation & Setup

### Option 1: Docker Deployment (Recommended)
The safest and easiest way to spin up this vulnerable environment is by using the provided Docker configuration.
1. Clone this repository to your local machine.
2. Ensure Docker and Docker Compose are installed on your system.
3. Build and run the containers using:
   `docker-compose up --build`
4. Access the web application via your browser (typically at `http://localhost:5000` or the port specified in the compose file).

### Option 2: Local Python Setup
1. Clone the repository to your local machine.
2. Install the required Python dependencies:
   `pip install -r requirements.txt`
3. Initialize and upgrade the database utilizing the provided migrations:
   `flask db upgrade`
4. Launch the application server:
   `python app.py`

## Security Disclaimer
**WARNING:** This project contains severe security flaws and is intentionally vulnerable by design. **Do not deploy this application on a public-facing web server, a production environment, or any untrusted network.** It is intended strictly for authorized educational purposes, ethical hacking practice, and local penetration testing.
