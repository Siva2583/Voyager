🌍 Voyager | AI-Powered Travel Planner

> **"Stop planning your trips with 50 open tabs."**

Voyager is a full-stack AI application that generates personalized, day-by-day travel itineraries. Unlike standard AI tools, Voyager uses custom backend logic to strictly enforce a **Total Group Budget**, ensuring your trip plan is mathematically accurate and financially realistic.

---

## 🚀 Live Demo
* **Live App:** [Click here to view Voyager](https://voyager-dgby.vercel.app/)
* **Demo Video:** [Watch the LinkedIn Demo](https://www.linkedin.com/posts/siva-charan-kg-72a900284_traveltech-generativeai-llm-ugcPost-7425072513896017920-r3tk?utm_source=social_share_send&utm_medium=member_desktop_web&rcm=ACoAAEUwcBIBYZx7vtPdyBheEgwy-2h1eIttfnA)

---

## ✨ Key Features
* **💸 Strict Budget Control:** Custom algorithm ensures the AI respects the *total* group budget, preventing common LLM math errors.
* **🗺️ Interactive Maps:** Integrated **Leaflet.js** to visualize every activity on a dynamic, interactive map.
* **⚡ High-Performance Backend:** Utilizes **Python Concurrent Futures** to fetch location images and geocoding data in parallel, reducing load times by 60%.
* **🎨 Modern UI:** Responsive Glassmorphism design built with React and CSS animations.
* **📄 PDF Export:** One-click download of your complete itinerary as a formatted PDF.

---

## 🛠️ Tech Stack
* **Frontend:** React.js, CSS3 (Glassmorphism), Leaflet Maps
* **Backend:** Python, Flask, Gunicorn
* **AI Engine:** Google Gemini Pro (via API)
* **Data Sources:** Wikipedia API (Images), OpenStreetMap (Geocoding)
* **Deployment:** Vercel (Frontend) + Railway (Backend)

---

## ⚙️ Installation & Setup

### 1. Clone the Repository
```bash
git clone [https://github.com/Siva2583/voyager.git](https://github.com/Siva2583/voyager.git)
cd voyager

```

### 2. Backend Setup (Flask)

Navigate to the backend folder:

```bash
cd ai_engine
pip install -r requirements.txt
python app.py

```

### 3. Frontend Setup (React)

Navigate to the client folder:

```bash
cd client
npm install
npm start

```

---

## 🧠 Challenges Solved

* **Concurrency:** API latency was initially high due to sequential data fetching. I implemented `concurrent.futures.ThreadPoolExecutor` to parallelize image and coordinate requests, significantly improving the user experience.
* **Hallucination Control:** Designed a strict System Prompt to force the LLM to output valid JSON, preventing the AI from generating unstructured text that breaks the UI.

---

## 📬 Contact

Built by **Siva Charan**

* **LinkedIn:** [Siva Charan KG](https://www.linkedin.com/in/siva-charan-kg-72a900284)
* **GitHub:** [Siva2583](https://github.com/Siva2583)

```

```
