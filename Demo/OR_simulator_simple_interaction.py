from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL, XSD
from pyshacl import validate
import time
import queries
from owlready2 import get_ontology, sync_reasoner, sync_reasoner_pellet
import json
from pynput import keyboard

OR = Namespace("http://www.semanticweb.org/Twin_OR/")

class ORSimulator:
    def __init__(self, ontology_path, shacl_shape_path, show_validation_report = False):
        self.input_ontology_path = ontology_path
        self.materialized_ontology_path = "working_ontology.owl"
        self.namespace = "http://www.semanticweb.org/Twin_OR/"
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
        self.or_graph = self.load_ontology_and_create_working_ontology(self.input_ontology_path, self.namespace, self.prefix)

        #Load SHACL shapes
        shacl_shapes_graph = Graph()
        self.shacl_shapes_graph = shacl_shapes_graph.parse(shacl_shape_path)

        #Load sensor data
        with open('sensor_data.json') as file:
            self.sensor_data = json.load(file)


    def load_ontology_and_create_working_ontology(self, file_path, namespace, prefix, format="xml"):
        """
        Loads ontology from input file with owlready library. The loaded ontology is reasoned with owlready
        and then saved to a working ontology file. Load from this file into owlready to obtain a working
        ontology called or_graph.
        """
        ontology = get_ontology(self.input_ontology_path).load()

        #Apply reasoner and save the ontology with inferences
        with ontology:
            sync_reasoner(infer_property_values = True)
            #Pellet reasoner below: uncomment to use it (and comment out the line above)
            # sync_reasoner_pellet(infer_property_values = True, infer_data_property_values = True) 

        ontology.save(self.materialized_ontology_path, format="rdfxml")

        #Load materialized (working) graph with RDFlib
        graph_or = Graph()
        graph_or.parse(self.materialized_ontology_path, format)
        ns = Namespace(namespace)

        return graph_or

        
    def simulate_robotic_sensor_output_and_update_ontology(self):
        """
        Retrieve data from json and update the ontology accordingly
        """

        for step_ID in self.current_steps:
            #Extract data relevant to a step
            step_data = self.sensor_data.get(step_ID, None)

            if step_data is not None:
                triples = step_data.get("triples", [])

                for triple in triples:
                    triple = self.parse_json_to_rdflib(triple)

                    act = step_data.get("action")

                    if act == "add":
                        self.or_graph.add(triple)
                    elif act == "remove":
                        self.or_graph.remove(triple)      


    def parse_json_to_rdflib(self, json_triple):
        s = OR[json_triple.get("subject")]
        p = OR[json_triple.get("predicate")]
        o = json_triple.get("object")

        if isinstance(o, bool):
            o = Literal(o, datatype=XSD.boolean)
        else:
            o = OR[json_triple.get("object")]

        rdflib_triple = (s, p, o)

        return rdflib_triple


    def respond_to_validation_report(self, validation_report):

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
                        
                          

        #default message:
        # message = "Something is going wrong!"
        # print(message)



    def violation_handling(self):
        for step_ID in self.current_steps:
            #Extract data relevant to a step
            step_data = self.sensor_data.get(step_ID, None)

            if step_data is not None:
                triples = step_data.get("triples", [])

                for triple in triples:
                    triple = self.parse_json_to_rdflib(triple)

                    act = step_data.get("action")

                    #reverse the action to fix the validation report
                    if act == "add":
                        self.or_graph.remove(triple)
                    elif act == "remove":
                        self.or_graph.add(triple)

        self.violation_occurred = False

        print("Looks like you've fixed the issue! We can now proceed.")


    def handle_new_sensor_data(self):
        """
        Activated whenever new sensor data is available
        """
        is_valid, validation_report = self.validate()

        if self.show_validation_report and not is_valid: #show validation report
            print(validation_report)
    
        #trigger an action if validation report is not empty
        if not is_valid:
            self.violation_occurred = True
            self.respond_to_validation_report(validation_report)
            self.violation_handling()
            is_valid, validation_report = self.validate()
        
        step_actions = self.get_step_actions(self.current_steps)

        if len(step_actions) == 1:
            step_action_msg = "(" + str(step_actions[0]) + ") is "
        else:
            step_action_msg = "s (" + ", ".join(step_actions[:-1]) + " and " + step_actions[-1] + ") are "

        print("Current step{}finished.\n[Press 'Tab' to proceed to the next step and '?' to ask a question.]".format(str(step_action_msg)))
    

    def validate(self):
        #validate updated ontology with SHACL
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
        query_result = list(self.or_graph.query(queries.get_next_steps(current_steps)))
        next_steps = self.query_result_to_list(query_result)

        return next_steps
    

    def query_result_to_list(self, query_result):
        result_list = []
        for row in query_result:
            for i in range(len(row)):
                local_name = self.get_local_name(row[i])
                result_list.append(local_name)
        return result_list
        

    def proceed_to_next_phase(self):
        query_result = self.or_graph.query(queries.get_next_phase_and_phase_order_no(self.current_phase, self.current_plan))
        first_steps = []

        current_phase_task = self.get_phase_task(self.get_local_name(self.current_phase))
        print(f"Current phase ({current_phase_task}), is complete.\n\n")
        
        for row in query_result:
            next_phase_task = self.get_phase_task(self.get_local_name(row.next_phase))
            print(f"Proceeding from phase {row.current_phase_no} to phase {row.next_phase_no}, namely {next_phase_task}.")
            self.current_phase = self.get_local_name(row.next_phase)
            
            #Initialize first steps of the phase
            init_step = self.get_local_name(row.first_step)
            first_steps.append(init_step) 

            if row.co_occurring_step is not None:
                co_occurring_step = self.get_local_name(row.co_occurring_step)
                first_steps.append(co_occurring_step) 

        self.current_steps = first_steps
    

    def get_local_name(self, uri):
        uri_str = str(uri)
        return uri_str.split('/')[-1]


    def get_phase_task(self, phase):
        query_result = self.or_graph.query(queries.get_phase_task(phase))
        for row in query_result:
            task = self.get_local_name(row.task).replace("_", " ")
        return task


    def get_step_actions(self, steps):
        step_actions = []
        
        for step in steps:
            query_result = self.or_graph.query(queries.get_step_action(step))
            for row in query_result:
                step_actions.append(self.get_local_name(row.action).replace("_", " "))
        
        return step_actions


    def intro_message(self):
        task_action = self.get_phase_task(self.current_phase)
        step_actions = self.get_step_actions(self.current_steps)

        if len(step_actions) == 1:
            step_action_msg = " is " + str(step_actions[0])
        else:
            step_action_msg = "s are " + ", ".join(step_actions[:-1]) + " and " + step_actions[-1]


        print(f"\nLet's begin the procedure. We're starting with phase 1, {task_action}.")
        print(f"The first step{str(step_action_msg)}")


    def progress_message(self, intro=False):

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
        """Check if the current phase is the final phase and quit if so."""
        query = queries.is_final_phase(self.current_phase)
        is_last_phase = bool(self.or_graph.query(query))
        return is_last_phase
    

    def setup_keyboard_listeners(self):
        self.listener = keyboard.Listener(on_press=self.on_key_press)
        self.listener.start()

    
    def on_key_press(self, key):
        """Handle key press events for interaction."""
        try:
            if key == keyboard.Key.tab and self.ongoing_procedure and not self.violation_occurred: #to the next step/phase
                self.progress()
            elif key.char == '?' and not self.violation_occurred and not self.in_question_mode:
                self.ask_question()
            elif key == keyboard.Key.esc:
                self.ongoing_procedure = False
                print("\nProcedure terminated.") 
                self.stop_listener()
                return False
        except AttributeError:
            pass


    def progress(self):

        #After handling the sensor data and validation, proceed to the next step or phase
        self.proceed_to_next_step()

        if self.ongoing_procedure:
            self.progress_message()

            #simulate sensor data
            self.simulate_robotic_sensor_output_and_update_ontology()
            
            #trigger listening function with updated sensor data
            self.handle_new_sensor_data()

    
    def ask_question(self): #TODO: add zooming in, reajusting of camera questions, "what is the next step?"
        self.in_question_mode = True
        question = input('\nIn question mode. What is your question?\n').strip().lower()

        #Questions about the next step
        if 'next step' in question:
            next_steps = self.get_next_steps(self.current_steps)

            if len(next_steps) == 0:
                print("There are no more steps to perform in this phase.")
            elif 'tool' in question: #ask about tools for next step
                query_result = self.or_graph.query(queries.get_tools_for_steps(next_steps))
                next_step_tools = self.query_result_to_list(query_result)

                if len(next_step_tools) == 0:
                    print("I don't know of any tools needed for the next step.")
                else:
                    print(f"Tools needed for the next step: {', '.join(next_step_tools)}")

            elif 'actor' in question: #ask about which actors need to be present
                query_result = self.or_graph.query(queries.get_actors_for_steps(next_steps))
                next_step_actors = self.query_result_to_list(query_result)

                if len(next_step_actors) == 0:
                    print("I don't know of any actors needed for the next step.")
                else:
                    print(f"Actors needed for the next step: {', '.join(next_step_actors)}")
            elif 'capability' in question or 'capabilities' in question: #ask about capabilities necessary for next step
                query_result = self.or_graph.query(queries.get_capabilities_for_steps(next_steps))
                next_step_capabilities = self.query_result_to_list(query_result)   

                if len(next_step_capabilities) == 0:
                    print("I don't know of any capabilities needed for the next step.")
                else:
                    print(f"Actors in the next step(s) must have the following capabilities: {', '.join(next_step_capabilities)}")

            elif 'material' in question: #ask about materials needed for next step
                query_result = self.or_graph.query(queries.get_materials_for_steps(next_steps))
                next_step_materials = self.query_result_to_list(query_result)   

                if len(next_step_materials) == 0:
                    print("I don't know of any materials needed for the next step.")
                else:
                    print(f"Materials needed for the next step: {', '.join(next_step_materials)}")
        else:
            "Sorry, I don't know how to answer that question."

        self.in_question_mode = False
        print("[Press 'Tab' to proceed and '?' to ask another question.]\n")

    
    def stop_listener(self):
        if self.listener is not None:
            self.listener.stop()


    def run_simulation(self):
        self.intro_message()
        self.setup_keyboard_listeners()

        #execute first step. Later, proceeding to next steps is triggered by pressing a 'Tab' key
        self.progress_message(intro=True)      
        self.simulate_robotic_sensor_output_and_update_ontology() #simulate sensor data
        self.handle_new_sensor_data() 

        while self.ongoing_procedure:
            time.sleep(0.1) #TODO: check if necessary

        self.stop_listener()

            