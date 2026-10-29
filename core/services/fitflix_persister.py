class FitFlixPersister:

    def persister(self, results):
        

        for result in results:
            if not result.matched:
                continue