🚀 How to Setup the Environment
Prerequisites
Python 3.10+
Node.js 18+
Google Gemini API Key

1. Repository & Virtual Environment
Bash
# Clone the repository
git clone https://github.com/Csyeoh/Rescue.git
cd Rescue/rescue_swarm_sim
# Create the virtual environment
python -m venv venv
# Activate the virtual environment (Windows):
venv\Scripts\activate  
# Activate the virtual environment (Mac/Linux):
source venv/bin/activate

2. Install Backend Dependencies
Bash
pip install mesa fastapi uvicorn fastmcp google-genai python-dotenv

3. Configure API Keys
Create a .env file in the root backend directory (rescue_swarm_sim) and add your Gemini API Key:
GEMINI_API_KEY="your_api_key_here"

4. Setup the Frontend Dashboard
Navigate to the UI folder to install the necessary Node dependencies:

Bash
cd ../rescue-ui
npm install
cd ../rescue_swarm_sim

🏃‍♂️ How to Run the Project
Launch the System
Run the master orchestrator script from the rescue_swarm_sim directory (ensure your Python virtual environment is still active). This will simultaneously boot the FastAPI server, initialize the database, and start the Next.js frontend.

Bash
python main.py

Once the terminal confirms all systems are nominal, you can access the application at:
Live Dashboard: http://localhost:3000
Backend API: http://localhost:8000
Note: To cleanly shut down all servers, simply press Ctrl+C in the terminal.