import subprocess
import yaml
import os
import random
import concurrent.futures
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

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

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
                self.workflow_data = yaml.safe_load(f)
        except FileNotFoundError:
            self.logger.error(f"Workflow file not found: {workflow_file}")
            return

        steps = self.workflow_data.get('workflow', {}).get('steps', [])
        self.current_step_index = 0; # reset the current step index
        while self.current_step_index < len(steps):
             step = steps[self.current_step_index]
             self.logger.info(f"Executing step: {step.get('name', step.get('id', ''))}")
             self._execute_step(step)
             if step.get('type') != 'goto':
                 self.current_step_index +=1 # Increment only if it is not a goto step.

    def _execute_step(self, step):
         step_type = step.get('type')
         step_id = step.get('id')
         try:
           if step_id:
              self.context[step_id + '.output'] = "" # Initialize the output in context before execution
           if step_type == 'system_command':
                  self._execute_system_command(step)
           if step_id:
              self.context[step_id + '.output'] = self.context.get(step_id + '.output',"") # Update the context before execution
           elif step_type == 'parallel_for_each':
              self._update_context_before_step(step)
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
           elif step_type == 'for_loop':
                self._execute_for_loop(step)
           elif step_type == 'while_loop':
                self._execute_while_loop(step)
           elif step_type == 'do_while_loop':
               self._execute_do_while_loop(step)
           elif step_type == 'set_variable':
               self._execute_set_variable(step)
           elif step_type == 'increment_variable':
               self._execute_increment_variable(step)
           elif step_type == 'goto':
              self._execute_goto(step)
           elif step_type == 'parallel_for_each':
             self._execute_parallel_for_each(step)
           elif step_type == 'parallel_and_branch':
              self._execute_parallel_and_branch(step)
           elif step_type == 'parallel_or_branch':
              self._execute_parallel_or_branch(step)
           elif step_type == 'split_list':
              self._execute_split_list(step)
           elif step_type == 'label':
              pass #do nothing
           else:
              self.logger.warning(f"Unsupported step type: {step_type}")
         except Exception as e:
           self.logger.error(f"Error executing step {step_id} : {e}")
    def _update_context_before_step(self,step):
        steps = self.workflow_data.get('workflow', {}).get('steps', [])
        for index, workflow_step in enumerate(steps):
            if workflow_step.get('id') == step.get('id'):
                if index > 0:
                    previous_step = steps[index-1]
                    if previous_step.get('id'):
                        self.context[previous_step.get('id') + '.output'] = self.context.get(previous_step.get('id') + '.output',"")
                break

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
        directory = self._resolve_template(step.get('directory'))
        if directory:
            command = f"cd {directory} && {command}"
        self.logger.info(f"Executing system command: {command}")
        try:
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate()
            if stderr:
                self.logger.warning(f"System command stderr: {stderr.strip()}")
            
            output_path = step.get('output_path')
            if output_path:
                output_path = os.path.join(self.output_dir, output_path)
                with open(output_path, 'a') as f:
                    f.write(stdout)
                with open(output_path, 'r') as f:
                    file_content = f.read()
                    self.logger.info(f"System command stdout: {stdout.strip()}, file content: {file_content.strip()}")
                    if step.get('id'):
                        self.context[step.get('id') + '.output'] = file_content.strip()
            else:
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
    def _execute_for_loop(self, step):
        loop_variable = step.get('variable')
        start = int(step.get('start'))
        end = int(step.get('end'))
        increment = int(step.get('increment'))
        loop_steps = step.get('steps', [])
        self.logger.info(f"Executing for loop with {loop_variable}, start: {start}, end:{end}, increment: {increment}")
        for i in range(start, end, increment):
            self.context[loop_variable] = i
            for loop_step in loop_steps:
                self._execute_step(loop_step)


    def _execute_while_loop(self, step):
          condition = self._resolve_template(step.get('condition'))
          loop_steps = step.get('steps',[])
          self.logger.info(f"Executing while loop with condition: {condition}")
          try:
               while eval(condition):
                   for loop_step in loop_steps:
                      self._execute_step(loop_step)
                   condition = self._resolve_template(step.get('condition'))  # Refresh the condition after loop iteration.
               self.logger.info(f"While loop terminated with condition {condition} becoming false")
          except Exception as e:
             self.logger.error(f"Error while loop execution: {e}")


    def _execute_do_while_loop(self, step):
        condition = self._resolve_template(step.get('condition'))
        loop_steps = step.get('steps', [])
        self.logger.info(f"Executing do-while loop with condition: {condition}")

        try:
            while True:
              for loop_step in loop_steps:
                self._execute_step(loop_step)
              condition = self._resolve_template(step.get('condition')) # Refresh the condition after loop iteration.
              if not eval(condition):
                  break
            self.logger.info(f"Do-while loop terminated with condition {condition} becoming false")

        except Exception as e:
             self.logger.error(f"Error do-while loop execution: {e}")

    def _execute_set_variable(self, step):
        variable = step.get('variable')
        value = self._resolve_template(step.get('value'))
        self.logger.info(f"Setting variable: {variable} to value {value}")
        self.context[variable] = value

    def _execute_increment_variable(self, step):
        variable = step.get('variable')
        amount = int(step.get('amount'))
        self.logger.info(f"Incrementing variable: {variable} by {amount}")
        if variable in self.context:
           self.context[variable] = int(self.context[variable]) + amount
        else:
            self.logger.warning(f"Variable not set {variable} and set to default value 0")
            self.context[variable] = amount
    def _execute_goto(self, step):
        target = step.get('target')
        self.logger.info(f"Executing goto : {target}")
        steps = self.workflow_data.get('workflow', {}).get('steps', [])
        for index,workflow_step in enumerate(steps):
          if workflow_step.get('id') == target:
              self.current_step_index = index
              return
        self.logger.warning(f"Goto target {target} not found in the workflow")

    def _execute_split_list(self, step):
         list_source = self._resolve_template(step.get('list_source'))
         if isinstance(list_source, str) :
             self.logger.warning(f"list_source is a string rather than list")
             list_source = [list_source]
         groups = step.get('groups',{})
         self.logger.info(f"Spliting the list into groups {groups}")
         group_list = self._split_list_by_percentage(list_source,groups)
         self.context[step.get('id') + '.output_groups'] = group_list # add to the context for future steps

    def _split_list_by_percentage(self, items, group_percentages):
         shuffled_items = list(items)
         random.shuffle(shuffled_items)

         total_items = len(shuffled_items)
         groups = []
         start = 0
         for group_id, percentage in group_percentages.items():
             num_items = int((percentage / 100) * total_items)
             end = start + num_items
             group_items = shuffled_items[start:end]
             groups.append({"id": group_id, "items": group_items})
             start = end

         # Add remaining items to the last group
         if start < total_items:
             last_group = groups[-1]
             remaining_items = shuffled_items[start:]
             last_group["items"].extend(remaining_items)


         return groups
    def _execute_parallel_for_each(self, step):
        list_source = self._resolve_template(step.get('list_source'))
        item_variable = step.get('item_variable')
        loop_steps = step.get('steps',[])
        self.logger.info(f"Executing parallel for each step")
        if isinstance(list_source, str) :
            self.logger.warning(f"list_source is a string rather than list")
            list_source = [list_source]

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for item in list_source:
                self.context[item_variable] = item
                future = executor.submit(self._execute_steps_list_in_branch,loop_steps)
                futures.append(future)
            concurrent.futures.wait(futures) # Wait for all threads to finish.

    def _execute_parallel_and_branch(self, step):
        branches = step.get('branches',[])
        self.logger.info(f"Executing parallel and branches ")
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for branch in branches:
                branch_steps = branch.get('steps',[])
                future = executor.submit(self._execute_steps_list_in_branch,branch_steps)
                futures.append(future)
            concurrent.futures.wait(futures) # Wait for all threads to finish.

    def _execute_parallel_or_branch(self, step):
         branches = step.get('branches',[])
         self.logger.info(f"Executing parallel or branches ")
         with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for branch in branches:
                    branch_steps = branch.get('steps',[])
                    future = executor.submit(self._execute_steps_list_in_branch,branch_steps)
                    futures.append(future)
                done, _ = concurrent.futures.wait(futures, return_when = concurrent.futures.FIRST_COMPLETED) # Wait for the first thread to complete
                self.logger.info(f"At least one branch has completed execution")


    def _execute_steps_list_in_branch(self, steps):
        try:
          for step in steps:
             self._execute_step(step)
        except Exception as e:
              self.logger.error(f"Error with branch execution: {e}")
