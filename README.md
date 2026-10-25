# Kasihub 🇿🇦

**A community resilience app for Diepsloot.**
**Built in 48 hours at FNB aoty hackthon by:** Mpho Mnguni, Tsholofelo, and Amukelani

## 🏗️ The Idea

We built this during FNB aoty hackathon over a single weekend. The whole thing started when one of us got home from the venue mid-load-shedding and realized we had no idea if the local shops were even open or had stock before walking there in the dark.

Everyone in our area finds out about outages from WhatsApp groups that are always two hours late. So we spent 48 hours building something slightly less chaotic.

Kasihub (means "Love Hub" in Sesotho) is a web app where people can see what's happening in their area, report issues like broken transformers or crime, and find out which local stores still have power and water.

## 🧠 What It Does

*   **Risk Prediction:** We built a scoring system that checks your water level, power status, and area to give you a "Risk Score." If your water is low and power is scheduled off, it tells you exactly what to prep.
*   **Live Reports:** Users post issues (Power, Water, Crime). Public Service accounts (like SAPS) can mark them as "Resolved."
*   **Store Status:** Business owners update their own store's power and water so people know where to go before walking 40 minutes for nothing.
*   **Outage Schedule:** Shows planned load shedding and water maintenance per zone.
*   **Emergency Services:** Quick-dial numbers for SAPS, clinic, fire, ambulance.
*   **Resource Sharing:** See who nearby has surplus water (>80%) and might be able to help.

## 👥 How We Split the Work

With only 48 hours we had to divide things up fast:

*   **Mpho mnguni (Backend & Database):** Handled Flask, SQLite, login sessions, and the ownership logic so only a store's actual owner can update its status. Also wrote the risk-scoring algorithm.
*   **[Tsholofelo and Amukelani] (Frontend & UI):** Built all the HTML, CSS, and JavaScript. Made sure the dashboard updates live after login and caught the XSS bug where someone could inject code through a report title.
*   **Me (Integration & Deployment):** Connected frontend to backend, handled user sessions so you don't re-login on refresh, and got us deployed on Render at like 3am on Sunday. Did final testing between judging rounds.

## 🛠️ Tech Stack

*   **Backend:** Python + Flask — lightweight, easy to spin up fast
*   **Database:** SQLite — file-based, zero setup, perfect for a hackathon
*   **Frontend:** Vanilla JavaScript — no React, no build step, just raw JS because we didn't have time to configure a framework
*   **CSS:** Custom properties + flexbox + grid
*   **Deployment:** Render.com free tier

No frameworks on purpose. Honestly if we'd tried to set up React + a proper database we probably wouldn't have finished.

## 🚀 How to Run It Locally

### 1. Prerequisites
Make sure you have **Python 3** installed. Check with:
```bash
python --version
