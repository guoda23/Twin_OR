from rdflib import Graph

def get_all_existing_tools():
    all_existing_tools = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX or: <http://www.semanticweb.org/Twin_OR/>
    select distinct ?tool where {
        ?step or:toolUsed ?tool .
    } limit 100
    """
    return all_existing_tools

def retrieve_all_steps():
    all_steps = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX or: <http://www.semanticweb.org/Twin_OR/>
    select ?step where {
        ?step a or:Step .
    } limit 100
    """
    return all_steps

def get_next_steps(current_steps): 
    step_conditions = ",".join(f"or:{step}" for step in current_steps)

    next_steps = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX or: <http://www.semanticweb.org/Twin_OR/>
    SELECT DISTINCT ?next_step ?co_occurring_step WHERE {{
        {{
            # Condition 1: Find steps that follow any of the current steps
            ?next_step or:follows ?current_step .
            FILTER(?current_step IN ({step_conditions}))

        }}
        UNION
        {{
            # Condition 2: Find steps that are followed by any of the current steps
            ?current_step or:followedBy ?next_step .
            FILTER(?current_step IN ({step_conditions}))

        }}
        OPTIONAL {{
            # Condition 3: Find co-occurring steps
            ?next_step or:co-occur ?co_occurring_step .

        }}
        OPTIONAL {{
            # Co-occurrence in the reverse direction
            ?co_occurring_step or:co-occur ?next_step .
        }}
    }} LIMIT 100
    """
    return next_steps

def get_next_phase_and_phase_order_no(current_phase, current_plan):
    
    result = f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX or: <http://www.semanticweb.org/Twin_OR/>
    SELECT DISTINCT ?next_phase ?current_phase_no ?next_phase_no ?first_step ?co_occurring_step WHERE {{
        or:{current_phase} or:phaseOrder ?current_phase_no .
        ?next_phase or:phaseOrder ?next_phase_no .
        FILTER (?next_phase_no = ?current_phase_no + 1).
        or:{current_plan} or:hasPhase ?next_phase .
        
        ?next_phase or:phaseStartStep ?first_step .
        
        OPTIONAL {{
            ?first_step or:co-occur ?co_occurring_step .

        }}
        OPTIONAL {{
            ?co_occurring_step or:co-occur ?first_step .
        }}
    }} LIMIT 100"""
    return result

def get_phase_task(phase):
    result = f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX or: <http://www.semanticweb.org/Twin_OR/>
    SELECT DISTINCT ?task WHERE {{
    or:{phase} or:phaseTask ?task
    }}
    LIMIT 100"""
    return result

def get_step_action(step):
    result = f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX or: <http://www.semanticweb.org/Twin_OR/>
    SELECT DISTINCT ?action WHERE {{
    or:{step} or:stepAction ?action
    }}
    LIMIT 100"""
    return result

def is_final_phase(current_phase):
    result = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX or: <http://www.semanticweb.org/Twin_OR/>
    ASK WHERE {{
        or:{current_phase} or:isFinalPhase true .
    }}
    """
    return result

    
