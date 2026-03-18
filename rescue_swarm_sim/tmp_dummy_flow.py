from crewai.flow.flow import Flow, start, listen

class DummyFlow(Flow):
    @start()
    def first_step(self):
        with open("dummy_executed.txt", "w") as f: f.write("FIRST STEP")
        return "step_one_done"

    @listen("step_one_done")
    def second_step(self):
        print("SECOND STEP")

if __name__ == "__main__":
    flow = DummyFlow()
    flow.kickoff()
