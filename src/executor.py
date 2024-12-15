import subprocess
import yaml
import os
from jinja2 import Template
import logging
import google.generativeai as genai
from playwright.sync_api import sync_playwright
from utils import create_directory


class WorkflowExecutor:
    def __init__(self, api_key, output_dir, log_dir):
        self.api_key = api_key
        self.output_dir = output_dir
        self.log_dir = log_dir
        self.context = {}
        genai.configure(api_key=self.api_key)

        create_directory(output_dir)
        create_directory(log_dir)
        self.logger = self.setup_logger()

    def setup_logger(self):
        logger = logging.getLogger('workflow_logger')
        logger.setLevel(logging.INFO)

        log_file = os.path.join(self.log_dir,"workflow_execution.log")
        file_handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        return logger


    def _resolve_template(self, text):
         if isinstance(text, str):
            template = Template(text)
            return template.render(self.context)
         return text



    def execute_workflow(self, workflow_file):
        self.logger.info(f"Starting workflow execution for {workflow_file}")
        try:
            with open(workflow_file, 'r') as f:
                workflow_data = yaml.safe_load(f)
        except FileNotFoundError:
            self.logger.error(f"Workflow file not found: {workflow_file}")
            return

        steps = workflow_data.get('workflow', {}).get('steps', [])
        for step in steps:
             self.logger.info(f"Executing step: {step.get('name', step.get('id', ''))}")
             self._execute_step(step)

    def _execute_step(self, step):
         step_type = step.get('type')
         step_id = step.get('id')
         try:
           if step_id:
              self.context[step_id + '.output'] = "" # Initialize the output in context before execution
           if step_type == 'browser_action':
                 self._execute_browser_action(step)
           elif step_type == 'system_command':
                  self._execute_system_command(step)
           elif step_type == 'gemini_analyze':
                self._execute_gemini_analyze(step)
           elif step_type == 'condition':
               self._execute_condition(step)
           elif step_type == 'notification':
                self._execute_notification(step)
           else:
                self.logger.warning(f"Unsupported step type: {step_type}")
         except Exception as e:
           self.logger.error(f"Error executing step {step_id} : {e}")

    def _execute_browser_action(self, step):
        action = step.get('action')
        if action == 'navigate':
           url = self._resolve_template(step.get('url'))
           self.logger.info(f"Navigating to {url}")
           self._execute_playwright(url=url)

        elif action == 'click':
            selector = self._resolve_template(step.get('selector'))
            self.logger.info(f"Clicking on {selector}")
            self._execute_playwright(selector=selector)

        elif action == 'enter_text':
             selector = self._resolve_template(step.get('selector'))
             text = self._resolve_template(step.get('text'))
             self.logger.info(f"Entering text '{text}' to {selector}")
             self._execute_playwright(selector=selector,text=text)

        elif action == 'wait':
             selector = self._resolve_template(step.get('selector'))
             timeout = int(step.get('timeout', 30))
             self.logger.info(f"Waiting for {selector}, with timeout of {timeout}")
             self._execute_playwright(selector=selector,timeout=timeout)
        else:
           self.logger.warning(f"Unsupported browser action: {action}")


    def _execute_playwright(self, url = None, selector=None, text=None, timeout=None):
      with sync_playwright() as p:
         browser = p.chromium.launch()
         page = browser.new_page()
         try:
            if url:
                page.goto(url)
            if selector and text:
                page.fill(selector, text)
            if selector and not text:
                 if timeout:
                   page.wait_for_selector(selector,timeout=timeout*1000)
                 else:
                    page.click(selector)

         except Exception as e:
            self.logger.error(f"Error with playwright execution:{e}")
         finally:
            browser.close()


    def _execute_system_command(self, step):
        command = self._resolve_template(step.get('command'))
        self.logger.info(f"Executing system command: {command}")
        try:
            if command.startswith("cd "):
                process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                stdout, stderr = process.communicate()
                if stderr:
                    self.logger.warning(f"System command stderr: {stderr.strip()}")
                self.logger.info(f"System command stdout: {stdout.strip()}")

            else:
                if os.name == 'posix':
                    if os.uname().sysname == 'Darwin':
                        # macOS
                        process = subprocess.Popen(['osascript', '-e', f'tell application "Terminal" to do script "{command}; bash"'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                        stdout, stderr = process.communicate()
                        if stderr:
                            self.logger.warning(f"System command stderr: {stderr.strip()}")
                        self.logger.info(f"System command stdout: {stdout.strip()}")

                    else:
                        # Linux
                        if command.startswith("cd "):
                            process = subprocess.Popen(['gnome-terminal', '--', 'bash', '-c', f'{command}; bash'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                        else:
                            process = subprocess.Popen(['gnome-terminal', '--', 'bash', '-c', f'{command}; bash'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                        stdout, stderr = process.communicate()
                        if stderr:
                            self.logger.warning(f"System command stderr: {stderr.strip()}")
                        self.logger.info(f"System command stdout: {stdout.strip()}")
                else:
                    # Other OS
                    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    stdout, stderr = process.communicate()
                    if stderr:
                        self.logger.warning(f"System command stderr: {stderr.strip()}")
                    self.logger.info(f"System command stdout: {stdout.strip()}")
            if step.get('id'):
                self.context[step.get('id') + '.output'] = stdout.strip()

        except Exception as e:
            self.logger.error(f"Error executing system command: {e}")

    def _execute_gemini_analyze(self, step):
        input_data = self._resolve_template(step.get('input'))
        prompt = self._resolve_template(step.get('prompt'))
        output_path = os.path.join(self.output_dir,step.get('output_path'))

        self.logger.info(f"Sending Gemini prompt: {prompt}, input : {input_data}")
        try:
              model = genai.GenerativeModel('gemini-pro')
              response = model.generate_content(prompt + " " + input_data)
              output = response.text.strip()
              self.context[step.get('id') + '.output'] = output # storing the gemini result in context.
              self.logger.info(f"Gemini Output: {output}")
              with open(output_path, 'w') as f:
                f.write(output)

        except Exception as e:
            self.logger.error(f"Error analyzing with Gemini : {e}")

    def _execute_condition(self, step):
         condition = self._resolve_template(step.get('condition'))
         self.logger.info(f"Evaluating condition {condition}")
         try:
              if eval(condition):
                self.logger.info(f"Condition {condition} evaluated to True")
                then_steps = step.get('then',[])
                for then_step in then_steps:
                   self._execute_step(then_step)
              else:
                self.logger.info(f"Condition {condition} evaluated to False")
                else_steps = step.get('else',[])
                for else_step in else_steps:
                    self._execute_step(else_step)

         except Exception as e:
                self.logger.error(f"Error evaluating condition {condition}, {e}")

    def _execute_notification(self, step):
       message = self._resolve_template(step.get('message'))
       self.logger.info(f"Sending notification: {message}")
       try:
           # Add logic here to send the notification using any notification service
           print(f"Notification Sent: {message}")
       except Exception as e:
              self.logger.error(f"Error sending notification message : {e}")
