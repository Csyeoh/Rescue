import os
from crewai import Agent, Task, Crew, LLM
from dotenv import load_dotenv
load_dotenv()

_llm = LLM(
    model="gemini/gemini-pro-latest",
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.0
)

agent = Agent(
    role="Tester",
    goal="Test tool calling",
    backstory="A testing agent",
    llm=_llm,
    verbose=True
)

task = Task(
    description="Say hello and tell me what the battery of drone_1 is. Use the tools if available, but if not just say you can't.",
    expected_output="A report on drone_1 battery",
    agent=agent
)

crew = Crew(agents=[agent], tasks=[task], verbose=True)
result = crew.kickoff()
print(f"RESULT: {result}")
