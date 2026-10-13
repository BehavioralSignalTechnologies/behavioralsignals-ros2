std_msgs/Header header  # stamp = time the result was received
string source           # "behavioral" | "deepfake"
int64 pid               # API process id, quoted in support requests
int32 message_id
InferenceResult[] results
