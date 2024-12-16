import os
from executor import WorkflowExecutor
import argparse
from utils import read_file

def main():
    parser = argparse.ArgumentParser(description="AI Automation Agent")
    parser.add_argument(
        "--workflow",
        type=str,
        required=True,
        help="Path to the workflow YAML file"
    )
    parser.add_argument(
        "--api_key",
        type=str,
        required=False,
        help="Gemini API key"
    )
    parser.add_argument(
        "--sudo_password",
        type=str,
        required=False,
        help="Sudo password"
    )
    args = parser.parse_args()

    workflow_file = args.workflow
    api_key = args.api_key if args.api_key else os.environ.get("GEMINI_API_KEY")
    sudo_password = args.sudo_password if args.sudo_password else os.environ.get("SUDO_PASSWORD")
    if not api_key:
        raise ValueError("Gemini API key not provided via --api_key or GEMINI_API_KEY environment variable")
    log_dir = os.path.join(os.getcwd(), 'log')
    output_dir = os.path.join(os.getcwd(),'output')


    executor = WorkflowExecutor(api_key,output_dir,log_dir, sudo_password)
    executor.execute_workflow(workflow_file)

if __name__ == "__main__":
    main()
