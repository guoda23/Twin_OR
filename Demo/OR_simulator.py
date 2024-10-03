from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL, XSD
from pyshacl import validate
import time
import queries
from owlready2 import get_ontology, sync_reasoner, sync_reasoner_pellet
import json

OR = Namespace("http://www.semanticweb.org/Twin_OR/")

class ORSimulator:
    def __init__(self, ontology_path, shacl_shape_path, data_generation_interval = 2, show_validation_report = False):
        self.input_ontology_path = ontology_path
        self.materialized_ontology_path = "working_ontology.owl"
        self.namespace = "http://www.semanticweb.org/Twin_OR/"
        self.prefix = "or"
        self.data_generation_interval = data_generation_interval
        self.current_steps = ["Step_A1_1", "Step_A1_2"]
        self.current_phase = "A_Phase1"
        self.current_plan = "PlanA"
        self.show_validation_report = show_validation_report
        self.ongoing_procedure = True

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

                    if description == "Step failure check":
                        affirming_help_msg = step_data.get("affirming help message", None)

                        if response == "yes":
                            print(affirming_help_msg)
                            time.sleep(2)
                        else:
                            print("Please try again.")
                        
                        self.progress_message()
                          

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

        #wait for 2 seconds
        time.sleep(2)
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
            self.respond_to_validation_report(validation_report)
            self.violation_handling()
            is_valid, validation_report = self.validate()
        
        step_actions = self.get_step_actions(self.current_steps)

        if len(step_actions) == 1:
            step_action_msg = "(" + str(step_actions[0]) + ") is "
        else:
            step_action_msg = "s (" + ", ".join(step_actions[:-1]) + " and " + step_actions[-1] + ") are "

        process_choice = input("Current step{}finished. Would you like to progress to the next step?".format(str(step_action_msg))).strip().lower()

        if process_choice == "yes":
            self.proceed_to_next_step()


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
        next_steps = []
        query_result = list(self.or_graph.query(queries.get_next_steps(self.current_steps)))
        
        test_val = not query_result
        
        if len(query_result) == 0: # If there are no steps to perform, move to next phase or end the procedure
            if self.is_final_phase() == True:
                print("No more steps needed. The final phase is complete. The procedure is finished.")
                self.ongoing_procedure = False
            else:
                self.proceed_to_next_phase()
        else:
            #Collect the next steps from the query results
            for row in query_result:
                for i in range(len(row)):
                    local_name = self.get_local_name(row[i])
                    next_steps.append(local_name)
        
            #Update
            self.current_steps = next_steps


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


    def progress_message(self):
        step_actions = self.get_step_actions(self.current_steps)

        if len(step_actions) == 1:
            step_action_msg = ": " + str(step_actions[0])
        else:
            step_action_msg = "s: " + ", ".join(step_actions[:-1]) + " and " + step_actions[-1]

        print(f"Performing step{str(step_action_msg)}...")


    def is_final_phase(self):
        """Check if the current phase is the final phase and quit if so."""
        query = queries.is_final_phase(self.current_phase)
        is_last_phase = bool(self.or_graph.query(query))
        return is_last_phase


    def run_simulation(self):
        self.intro_message()
        
        while self.ongoing_procedure:
            self.progress_message()

            time.sleep(2)
            
            #simulate sensor data
            self.simulate_robotic_sensor_output_and_update_ontology()
            
            #trigger listening function with updated sensor data
            self.handle_new_sensor_data()

            #wait a time period before new sensor data
            time.sleep(self.data_generation_interval)
            