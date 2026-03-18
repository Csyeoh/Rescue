import sys
import os

sys.path.append(os.path.abspath(os.getcwd()))

from swarm_flow.main import kickoff

if __name__ == "__main__":
    try:
        print("Starting manual kickoff...")
        kickoff()
    except Exception as e:
        import traceback
        traceback.print_exc()
