import queries
from ontology_utils import query_result_to_list
import re

def question_mode(or_simulator_instance, question):  #TODO: list the capabilities at the start
    """
    Handle user questions during simulation.

    Processes user questions related to the next steps in the procedure, such as 
    tools, actors, capabilities, or materials required. Utilizes the simulation 
    instance to retrieve relevant information and provides detailed responses.

    Args:
        or_simulator_instance (ORSimulator): The instance of the simulator handling 
            the current state and ontology graph.
        question (str): The user's question as a string.

    Outputs:
        Prints detailed responses to the user's question, such as:
        - The next steps in the procedure.
        - Tools, actors, capabilities, or materials required for the next step.
        - A default message if the question cannot be answered.
    """

    #Questions about the next step
    if 'next step' in question:
        next_steps = or_simulator_instance.get_next_steps(or_simulator_instance.current_steps)
        
        if len(next_steps) == 0:
            print("There are no more steps to perform in this phase.")
        elif 'tool' in question: #ask about tools for next step
            
            query_result = or_simulator_instance.or_graph.query(queries.get_tools_for_steps(next_steps))
            next_step_tools = query_result_to_list(query_result)
            
            if len(next_step_tools) == 0:
                print("I don't know of any tools needed for the next step.")
            else:
                print(f"Tools needed for the next step: {', '.join(next_step_tools)}")
        elif 'actor' in question: #ask about which actors need to be present
            query_result = or_simulator_instance.or_graph.query(queries.get_actors_for_steps(next_steps))
            next_step_actors = query_result_to_list(query_result)

            if len(next_step_actors) == 0:
                print("I don't know of any actors needed for the next step.")
            else:
                print(f"Actors needed for the next step: {', '.join(next_step_actors)}")
        elif 'capability' in question or 'capabilities' in question: #ask about capabilities necessary for next step
            query_result = or_simulator_instance.or_graph.query(queries.get_capabilities_for_steps(next_steps))
            next_step_capabilities = query_result_to_list(query_result)   

            if len(next_step_capabilities) == 0:
                print("I don't know of any capabilities needed for the next step.")
            else:
                print(f"Actors in the next step(s) must have the following capabilities: {', '.join(next_step_capabilities)}")
        elif 'material' in question: #ask about materials needed for next step
            query_result = or_simulator_instance.or_graph.query(queries.get_materials_for_steps(next_steps))
            next_step_materials = query_result_to_list(query_result)   

            if len(next_step_materials) == 0:
                print("I don't know of any materials needed for the next step.")
            else:
                print(f"Materials needed for the next step: {', '.join(next_step_materials)}")
        else:
            print("Sorry, I didn't understand the question.")
    elif 'zoom' in question:
        if 'in' in question:
            print("Zooming in...")
        elif 'out' in question:
            print("Zooming out...")
        else:
            print("Sorry, I didn't understand the question.")
    elif 'angle' or 'position':
        #checks if there is an already specified position
        match = re.search(r'\d+', question) 
        contains_integer = bool(match) 

        if contains_integer:
            print(f"Setting camera angle to position {int(match.group())}.")
        else:
            position = input("What position would you like to set the camera to? ")
            print(f"Setting camera angle to position {position}.")
    else:
        print("Sorry, I don't know how to answer that question.")
