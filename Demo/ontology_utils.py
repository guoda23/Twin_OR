from rdflib import Graph, Literal
from owlready2 import get_ontology, sync_reasoner, sync_reasoner_pellet
from rdflib.namespace import XSD

def load_and_materialize_ontology(file_path, format="xml", reasoner = "hermit"):
    """
    Load the ontology, perform reasoning on it, save it to a working ontology file and return
    a materialized RDFLib graph.

    Args:
        file_path (str): Path to the ontology file.
        namespace (Namespace): RDFLib Namespace object for the ontology (e.g., OR).
        prefix (str): Prefix for the namespace.
        format (str, optional): Format of the ontology file. Defaults to "xml".

    Returns:
        rdflib.Graph: A materialized ontology graph with inferred triples.
    """

    ontology = get_ontology(file_path).load()

        #Apply reasoner and save the ontology with inferences
    with ontology:
        if reasoner == "hermit":
            sync_reasoner(infer_property_values = True)
        elif reasoner == "pellet":
            sync_reasoner_pellet(infer_property_values = True, infer_data_property_values = True)

    materialized_ontology_path = "working_ontology.owl"
    ontology.save(materialized_ontology_path, format="rdfxml")

    #Load materialized (working) graph with RDFlib
    graph_or = Graph()
    graph_or.parse(materialized_ontology_path, format)

    return graph_or


def parse_json_to_rdflib(json_triple, namespace):
    """
    Convert a JSON triple data to an RDFLib triple.

    Args:
        json_triple (dict): A JSON representation of a triple.
        namespace (Namespace): RDFLib Namespace object for the ontology.

    Returns:
        tuple: An RDFLib triple (subject, predicate, object).
    """

    s = namespace[json_triple.get("subject")]
    p = namespace[json_triple.get("predicate")]
    o = json_triple.get("object")

    if isinstance(o, bool):
        o = Literal(o, datatype=XSD.boolean)
    else:
        o = namespace[json_triple.get("object")]

    rdflib_triple = (s, p, o)

    return rdflib_triple


def query_result_to_list(query_result):
    """
    Convert a SPARQL query result to a list of (human readable) names (extracts 
    labels for each URI in the result). Flatten the query result into a single
    list of labels.

    Args:
        query_result (iterable): A SPARQL query result, where each row contains one or more URIs.

    Returns:
        list: A flat list of labels extracted from the query result.
    """

    result_list = []
    for row in query_result:
        for i in range(len(row)):
            local_name = get_label_from_uri(row[i])
            result_list.append(local_name)
    return result_list


def get_label_from_uri(uri):
    """
    Get the label from a URI.

    Args:
        uri (URIRef): A URI to process.

    Returns:
        str: The label from the URI.
    """
    
    uri_str = str(uri)
    return uri_str.split('/')[-1]