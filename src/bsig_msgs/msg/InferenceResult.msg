string task             # emotion, positivity, strength, engagement, hesitation,
                        # speaking_rate, gender, age, intensity, deepfake. A "features" row with
                        # no label or numbers is an empty embedding placeholder; ignore it.
string final_label
string level            # "segment" | "utterance"
builtin_interfaces/Time start
builtin_interfaces/Time end
Prediction[] predictions
