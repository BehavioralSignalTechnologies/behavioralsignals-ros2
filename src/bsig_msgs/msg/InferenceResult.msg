string task             # emotion, positivity, strength, engagement, hesitation,
                        # speaking_rate, gender, age, intensity, deepfake
string final_label
string level            # "segment" | "utterance"
builtin_interfaces/Time start
builtin_interfaces/Time end
Prediction[] predictions
