import json
import time
from pynput import keyboard
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL, XSD
from pyshacl import validate

#local imports
import queries
from ontology_utils import load_and_materialize_ontology, parse_json_to_rdflib, query_result_to_list, get_label_from_uri
from question_mode import question_mode, display_question_menu


OR = Namespace("http://www.semanticweb.org/Twin_OR/")

class ORSimulator:
    def __init__(self, ontology_path, shacl_shape_path, show_validation_report = False):
        
        self.input_ontology_path = ontology_path
        self.materialized_ontology_path = "working_ontology.owl"
        self.prefix = "or"
        self.current_steps = ["Step_A1_1", "Step_A1_2"]
        self.current_phase = "A_Phase1"
        self.current_plan = "PlanA"
        self.show_validation_report = show_validation_report
        self.ongoing_procedure = True
        self.in_question_mode = False
        self.violation_occurred = False
        self.listener = None

        #Load the Twin OR ontology with RDFlib
        self.or_graph = load_and_materialize_ontology(self.input_ontology_path, OR, self.prefix)

        #Load SHACL shapes
        shacl_shapes_graph = Graph()
        self.shacl_shapes_graph = shacl_shapes_graph.parse(shacl_shape_path)

        #Load sensor data
        with open('sensor_data.json') as file:
            self.sensor_data = json.load(file)

        
    def simulate_robotic_sensor_output_and_update_ontology(self):
        """
        Simulate robotic sensor data and update the ontology accordingly.

        From a json file, retrieves simulated "sensor data" for the current steps, converts JSON
        data to RDFLib triples, and updates the ontology graph by adding or removing triples 
        according to simulated "sesnsor data".

        Args:
            None

        Updates:
            self.or_graph (rdflib.Graph): The ontology graph with added or removed triples.        
        """

        for step_ID in self.current_steps:
            #Extract data relevant to a step
            step_data = self.sensor_data.get(step_ID, None)

            if step_data is not None:
                triples = step_data.get("triples", [])

                for triple in triples:
                    triple = parse_json_to_rdflib(triple, OR)

                    act = step_data.get("action")

                    if act == "add":
                        self.or_graph.add(triple)
                    elif act == "remove":
                        self.or_graph.remove(triple)      


    def respond_to_violation(self):
        """
        Handle violations by extracting and displaying relevant messages.

        When a violation occurs, retrieves and prints a message alerting the user 
        and providing a description of the issue. Prompts the user for input to 
        resolve the issue, possibly offering further guidance based on the response.

        Args:
            None

        Updates:
            None
        """


        for step_ID in self.current_steps:
            #Extract message relevant to the step
            step_data = self.sensor_data.get(step_ID, None)

            if step_data is not None:
                message = step_data.get("message", None)
                description = step_data.get("description", None)
                
                if message is not None:
                    response = input(message).strip().lower()

                    if description in ("Step failure check", "Alignment check step", "Block positioning step"):
                        affirming_help_msg = step_data.get("affirming help message", None)

                        if "yes" in response:
                            print(affirming_help_msg)
                            time.sleep(2)
                        else:
                            print("Please try again.")
                        

    def post_violation_processing(self):
        """
        Restore the ontology graph to a non-violation state.

        Reverses the actions that caused the violation by either adding or 
        removing triples in the ontology graph. Resets the violation flag 
        and confirms the issue has been resolved.

        Args:
            None

        Updates:
            self.or_graph (rdflib.Graph): Restored to a consistent state.
            self.violation_occurred (bool): Set to False after processing.                
        """
    
        for step_ID in self.current_steps:
            #Extract data relevant to a step
            step_data = self.sensor_data.get(step_ID, None)

            if step_data is not None:
                triples = step_data.get("triples", [])

                for triple in triples:
                    triple = parse_json_to_rdflib(triple, OR)

                    act = step_data.get("action")

                    #reverse the action to fix the validation report
                    if act == "add":
                        self.or_graph.remove(triple)
                    elif act == "remove":
                        self.or_graph.add(triple)

        self.violation_occurred = False

        print("Looks like you've fixed the issue! We can now proceed.")


    def process_sensor_data_and_advance(self):
        """
        Process new sensor data, validate the updated ontology, and handle any
        violations before moving to the next step(s).

        Takes the updated graph with new sensor data and validates it with SHACL.
        If a violation is detected, the user is prompted to respond to the violation.
        Restores the graph after violation handling and prompts to move to the next step(s).
        
        Args:
            None

        Updates:
            self.violation_occurred (bool): Set to True if a violation is detected.
            self.or_graph (rdflib.Graph): May be updated during violation handling.

        Outputs:
            Prints the validation report (if enabled) and actions for the current steps.    
        """

        is_valid, validation_report = self.validate()

        if self.show_validation_report and not is_valid: #show validation report
            print(validation_report)
    
        #trigger an action if validation report is not empty
        if not is_valid:
            self.violation_occurred = True
            self.respond_to_violation()
            self.post_violation_processing()
            is_valid, validation_report = self.validate()
        
        step_actions = self.get_step_actions(self.current_steps)

        if len(step_actions) == 1:
            step_action_msg = "(" + str(step_actions[0]) + ") is "
        else:
            step_action_msg = "s (" + ", ".join(step_actions[:-1]) + " and " + step_actions[-1] + ") are "

        print("Current step{}finished.\n[Press 'Tab' to proceed to the next step and '?' to ask a question.]".format(str(step_action_msg)))
    

    def validate(self):
        """
        Validate the ontology graph against SHACL shapes.

        Uses SHACL rules to check if the ontology graph conforms to its constraints.
        Returns whether the graph conforms and a detailed validation report.

        Args:
            None

        Returns:
            tuple:
                conforms (bool): True if the graph conforms to the SHACL rules, False otherwise.
                validation_report (str): A human-readable report detailing validation results.
        """

        is_valid, _, validation_report = validate(self.or_graph, #TODO: distinction between data graph and schema graph (?)
        shacl_graph= self.shacl_shapes_graph,
        ont_graph=None,
        inference='rdfs',
        abort_on_first=False,
        allow_infos=False,
        allow_warnings=False,
        meta_shacl=False,
        advanced=False,
        js=False,
        debug=False)

        return is_valid, validation_report


    def proceed_to_next_step(self):
        """
        Advance to the next step(s) in the current phase.

        Retrieves the next steps through a SPARQL query and updates the simulation's
        state. If there are no more steps, flags the procedure for termination. Otherwise,
        updates the current steps and displays a message indicating the next steps.

        Args:
            None

        Updates:
            self.current_steps (list): Updated with the next steps in the procedure.
            self.ongoing_procedure (bool): Set to False if no more steps remain.

        Outputs:
            Prints a message indicating the next steps or the end of the phase.
        """

        next_steps = self.get_next_steps(self.current_steps)
        
        if len(next_steps) == 0: # If there are no steps to perform, move to next phase or end the procedure
            if self.is_final_phase() == True:
                print("No more steps needed. The final phase is complete. The procedure is finished.")
                self.ongoing_procedure = False
                self.stop_listener()
            else:
                self.proceed_to_next_phase()
        else:        
            #Update
            self.current_steps = next_steps

    
    def get_next_steps(self, current_steps):
        """
        Retrieve the next steps in the procedure.

        Executes a SPARQL query to determine the next steps based on the given 
        current steps. Converts the query result into a list of step labels.

        Args:
            current_steps (list): The current steps being executed in the procedure.

        Returns:
            list: A list of labels representing the next steps in the procedure.
        """
    
        query_result = list(self.or_graph.query(queries.get_next_steps(current_steps)))
        next_steps = query_result_to_list(query_result)

        return next_steps
        

    def proceed_to_next_phase(self):
        """
        Transition to the next phase of the simulation.

        Executes a SPARQL query to retrieve the next phase and its details, 
        including the initial steps. Updates the current phase and initializes 
        the first steps of the new phase. Displays information about the transition 
        from the current phase to the next.

        Args:
            None

        Updates:
            self.current_phase (str): Set to the next phase of the procedure.
            self.current_steps (list): Initialized with the first steps of the new phase.

        Outputs:
            Prints messages indicating the current phase completion, the next phase 
            transition, and the initialized steps of the new phase.
        """

        query_result = self.or_graph.query(queries.get_next_phase_and_phase_order_no(self.current_phase, self.current_plan))
        first_steps = []

        current_phase_task = self.get_phase_task(get_label_from_uri(self.current_phase))
        print(f"Current phase ({current_phase_task}), is complete.\n\n")
        
        for row in query_result:
            next_phase_task = self.get_phase_task(get_label_from_uri(row.next_phase))
            print(f"Proceeding from phase {row.current_phase_no} to phase {row.next_phase_no}, namely {next_phase_task}.")
            self.current_phase = get_label_from_uri(row.next_phase)
            
            #Initialize first steps of the phase
            init_step = get_label_from_uri(row.first_step)
            first_steps.append(init_step) 

            if row.co_occurring_step is not None:
                co_occurring_step = get_label_from_uri(row.co_occurring_step)
                first_steps.append(co_occurring_step) 

        self.current_steps = first_steps


    def get_phase_task(self, phase):
        """
        Retrieve the task label associated with a specific phase.

        Executes a SPARQL query to find the task corresponding to the given phase 
        and returns its label.

        Args:
            phase (str): The phase for which the task is being retrieved.

        Returns:
            str: The label of the task associated with the phase, or None if no task is found.
        """

        query_result = self.or_graph.query(queries.get_phase_task(phase))
        for row in query_result:
            task = get_label_from_uri(row.task).replace("_", " ")
        return task


    def get_step_actions(self, steps):
        """
        Retrieve the actions associated with specific steps.

        Executes a SPARQL query to determine the actions required for the given steps 
        and returns their labels as a list.

        Args:
            steps (list): A list of steps for which actions are being retrieved.

        Returns:
            list: A list of action labels associated with the given steps.
        """

        step_actions = []
        
        for step in steps:
            query_result = self.or_graph.query(queries.get_step_action(step))
            for row in query_result:
                step_actions.append(get_label_from_uri(row.action).replace("_", " "))
        
        return step_actions


    def intro_message(self):
        """
        Display the introductory message for the simulation, including the current
        phase and steps.

        Retrieves the current phase and step details and incorporates them into the 
        introductory message. Provides an overview of the simulation's purpose and 
        instructions for interacting with the system. #TODO: add more instructions

        Args:
            None

        Outputs:
            Prints the introductory message to the console.
        """

        task_action = self.get_phase_task(self.current_phase)
        step_actions = self.get_step_actions(self.current_steps)

        if len(step_actions) == 1:
            step_action_msg = " is " + str(step_actions[0])
        else:
            step_action_msg = "s are " + ", ".join(step_actions[:-1]) + " and " + step_actions[-1]


        print(f"\nLet's begin the procedure. We're starting with phase 1, {task_action}.")
        print(f"The first step{str(step_action_msg)}")


    def progress_message(self, intro=False):
        """
        Display a progress message for the current steps in the simulation.

        Constructs and prints a message indicating the actions for the current steps. 
        Optionally formats the message differently if called during the introduction.

        Args:
            intro (bool): If True, adds introductory formatting to the message. Defaults to False.

        Outputs:
            Prints the progress message for the current steps, including the actions to perform.
        """

        step_actions = self.get_step_actions(self.current_steps)

        if len(step_actions) == 1:
            step_action_msg = ": " + str(step_actions[0])
        else:
            step_action_msg = "s: " + ", ".join(step_actions[:-1]) + " and " + step_actions[-1]

        if intro:
            formating = "\t"
        else:
            formating = ""

        msg = formating +"Performing step" + str(step_action_msg) + "..."
        print(msg)


    def is_final_phase(self):
        """
        Check if the current phase is the final phase.

        Executes a SPARQL query to determine whether the current phase is the last 
        phase in the procedure.

        Args:
            None

        Returns:
            obol: True if the current phase is the final phase, False otherwise.
        """

        query = queries.is_final_phase(self.current_phase)
        is_last_phase = bool(self.or_graph.query(query))
        return is_last_phase
    

    def setup_keyboard_listeners(self):
        """
        Set up keyboard listeners for user interaction.

        Initializes a keyboard listener to capture key presses and assigns the 
        `on_key_press` method as the callback for key press events.

        Args:
            None

        Updates:
            self.listener (keyboard.Listener): The active keyboard listener instance.
        """
    
        self.listener = keyboard.Listener(on_press=self.on_key_press)
        self.listener.start()

    
    def on_key_press(self, key): #TODO: debug esc termination
        """
        Handle key press events during the simulation.

        Processes key presses to control the simulation, including progressing to 
        the next step or phase, entering question mode, or terminating the procedure.

        Args:
            key (keyboard.Key or keyboard.KeyCode): The key press event to process.

        Updates:
            self.ongoing_procedure (bool): Set to False if the procedure is terminated.

        Outputs:
            Prints messages based on user actions, such as termination or entering question mode.
        """

        try:
            if key == keyboard.Key.esc:
                self.ongoing_procedure = False
                print("\nProcedure terminated.") 
                self.stop_listener()
                return False
            
            if self.in_question_mode:
                return
            
            if key == keyboard.Key.tab and self.ongoing_procedure and not self.violation_occurred: #to the next step/phase
                self.advance_simulation()
            elif key.char == '?' and not self.violation_occurred and not self.in_question_mode:
                self.ask_question()
        except AttributeError:
            pass


    def advance_simulation(self):
        """
        Advance the simulation workflow to the next step or phase.

        Orchestrates the simulation's progression by:
        1. Transitioning to the next step or phase using `proceed_to_next_step`.
        2. Displaying progress messages for the current steps.
        3. Simulating sensor data and updating the ontology.
        4. Validating the updated ontology and addressing any violations.

        Ensures the simulation continues as long as the procedure remains active.

        Args:
            None

        Updates:
            self.current_steps (list): Updated to the next steps in the procedure.
            self.current_phase (str): Updated to the next phase if applicable.
            self.or_graph (rdflib.Graph): Modified during sensor data simulation.

        Outputs:
            Prints messages indicating the simulation's progress, including step or 
            phase transitions and any updates to the ontology.
        """

        #After handling the sensor data and validation,
        #proceed to the next step (or phase if no more steps in current phase)
        self.proceed_to_next_step()

        if self.ongoing_procedure:
            self.progress_message()
            self.simulate_robotic_sensor_output_and_update_ontology()
            self.process_sensor_data_and_advance()

    
    def ask_question(self):
        """
        Enter question mode to handle user inquiries.

        Prompts the user to enter a question and processes it using the question 
        handling logic. Temporarily stops the keyboard listener during question 
        mode to prevent interference with user input. Restarts the listener once 
        question mode ends.

        Args:
            None

        Updates:
            self.in_question_mode (bool): Set to True while in question mode and 
                reset to False after exiting.

        Outputs:
            Processes and responds to the user's question via console messages.
        """

        self.in_question_mode = True

        if self.listener:  # Stop the listener while in question mode
            self.listener.stop()

        display_question_menu()
        question = input('What is your question?\n').strip().lower()
        question_mode(self, question)

        self.in_question_mode = False
        print("[Press 'Tab' to proceed and '?' to ask another question.]\n")
        
        self.setup_keyboard_listeners() #restart the listener after question mode done


    def stop_listener(self):
        """
        Stop the keyboard listener.

        Terminates the active keyboard listener to prevent further key press events 
        from being processed.

        Args:
            None

        Updates:
            self.listener (keyboard.Listener): Stopped and deactivated.
        """
    
        if self.listener is not None:
            self.listener.stop()


    def run_simulation(self):
        """
        Run the simulation.

        Starts the simulation by setting up the keyboard listeners and displaying 
        the introductory message. Continuously processes user interactions and 
        simulation updates until the procedure is completed or terminated.

        Args:
            None

        Updates:
            self.listener (keyboard.Listener): Activated to capture user input.
            self.ongoing_procedure (bool): Determines whether the simulation continues.

        Outputs:
            Prints simulation progress, user prompts, and interaction responses.
        """

        self.intro_message()
        self.setup_keyboard_listeners()

        #execute first step. Later, proceeding to next steps is triggered by pressing a 'Tab' key
        self.progress_message(intro=True)      
        self.simulate_robotic_sensor_output_and_update_ontology() #simulate sensor data
        self.process_sensor_data_and_advance() 

        while self.ongoing_procedure:
            time.sleep(0.1) #TODO: check if necessary

        self.stop_listener()