from OR_simulator import ORSimulator

simulator = ORSimulator('or_ontology.owl', 'SHACL_constraints.ttl')

# Run a method to test the class
simulator.run_simulation()