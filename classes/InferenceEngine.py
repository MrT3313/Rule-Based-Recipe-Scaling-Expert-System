class InferenceEngine:
    def __init__(self, wm, kb, conflict_resolution_strategy='priority', verbose=True):
        self.working_memory = wm
        self.knowledge_base = kb
        self.cycle_count = 0
        self.conflict_resolution_strategy = conflict_resolution_strategy
        self.verbose = verbose

    def run(self):
        pass