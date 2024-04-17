import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from flwr.client import start_numpy_client, NumPyClient
import keras as ks

from utils import load_partition, load_testing_data, get_labels

# Make TensorFlow log less verbose
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

IMG_SIZE = 160

# Unique client identifier
client_id = int(sys.argv[1])  # Assuming client index is provided as an argument

# Load server address and port number from command-line arguments
server_address = "127.0.0.1"  # sys.argv[2]
port_number = "8080"  # int(sys.argv[3])

# Example usage
# python3 client.py 0 SERVER_IP_ADDRESS 8080

model = ks.Sequential([
    ks.layers.Conv2D(32, (3, 3), activation='relu', input_shape=(IMG_SIZE, IMG_SIZE, 1)),
    ks.layers.MaxPooling2D((2, 2)),
    ks.layers.Conv2D(64, (3, 3), activation='relu'),
    ks.layers.MaxPooling2D((2, 2)),
    ks.layers.Flatten(),
    ks.layers.Dense(128, activation='relu'),
    ks.layers.Dense(4, activation='softmax')
])

model.compile(
    optimizer='adam',
    loss=ks.losses.SparseCategoricalCrossentropy(from_logits=True),
    metrics=['accuracy']
)

if len(sys.argv) > 1:
    X_train, X_val, y_train, y_val = load_partition(int(sys.argv[1]))
else:
    print("Not enough arguments... expecting python3 client.py PARTITION_NUMBER; where partition number is 0, 1, 2, 3")
    sys.exit()

# Load testing data
X_test, y_test = load_testing_data()

# Get labels
labels = get_labels()


# Class to handle federated client
class FederatedClient(NumPyClient):
    def __init__(self):
        super().__init__()
        self.pre_fl_predicted_probs = None
        self.post_fl_predicted_probs = None
    def get_parameters(self, config):
        return model.get_weights()

    def fit(self, parameters, config):
        # Store predicted probabilities before federated learning
        self.pre_fl_predicted_probs = model.predict(X_val)

        model.set_weights(parameters)
        history = model.fit(X_train, y_train, epochs=100, batch_size=32, steps_per_epoch=5, validation_split=0.1)

        results = {
            "loss": history.history["loss"][0],
            "accuracy": history.history["accuracy"][0],
            "val_loss": history.history["val_loss"][0],
            "val_accuracy": history.history["val_accuracy"][0],
        }
        # Store predicted probabilities after federated learning
        self.post_fl_predicted_probs = model.predict(X_val)

        return model.get_weights(), len(X_train), results

    def evaluate(self, parameters, config):
        model.set_weights(parameters)
        loss, accuracy = model.evaluate(X_val, y_val)
        print("****** CLIENT ACCURACY: ", accuracy, " ******")
        return loss, len(X_val), {"accuracy": accuracy}

    def show_test_samples(self):
        # Create a dictionary to store the first occurrence of each class label
        first_occurrence = {}

        # Find the index of the first occurrence of each class label
        for class_label in range(len(labels)):
            indices = np.where(y_test == class_label)[0]
            if len(indices) > 0:
                first_occurrence[class_label] = indices[0]

        # Get the first images of each class label
        test_images = X_test[list(first_occurrence.values())]
        test_labels = y_test[list(first_occurrence.values())]

        # Predict labels for test samples
        predicted_labels = model.predict(test_images)
        predicted_labels = np.argmax(predicted_labels, axis=1)

        # Get the predicted probabilities for each class
        predicted_probs = model.predict(test_images)

        # Display test samples with true and predicted labels
        plt.figure(figsize=(12, 8))
        for i in range(len(first_occurrence)):
            plt.subplot(2, 3, i + 1)  # Assuming there are 6 classes, adjust accordingly
            plt.imshow(test_images[i], cmap='gray')
            true_label = labels[test_labels[i]]
            predicted_label = labels[predicted_labels[i]]
            accuracy = predicted_probs[i][predicted_labels[i]]
            plt.title(
                f"Client {client_id}\nTrue Label: {true_label}\nPredicted Label: {predicted_label}\nAccuracy: {accuracy:.2f}")
            plt.axis('off')
        plt.tight_layout()
        plt.show()

    def compare_predictions(self):
        if self.pre_fl_predicted_probs is None or self.post_fl_predicted_probs is None:
            print("Predicted probabilities not available.")
            return

        # Select the same four images for comparison
        indices = [0, 1, 2, 3]  # Adjust as needed

        # Display the predictions for each image
        plt.figure(figsize=(12, 8))
        for i, idx in enumerate(indices):
            plt.subplot(2, 2, i + 1)
            test_sample = X_test[idx]
            true_label = labels[y_test[idx]]  # Fetch the true label correctly
            pre_fl_prob = self.pre_fl_predicted_probs[idx]
            post_fl_prob = self.post_fl_predicted_probs[idx]
            pre_fl_label = labels[np.argmax(pre_fl_prob)]
            post_fl_label = labels[np.argmax(post_fl_prob)]
            plt.imshow(test_sample, cmap='gray')
            plt.title(
                f"Client {client_id}\nTrue Label: {true_label}\nBefore FL: {pre_fl_label} ({pre_fl_prob.max():.2f})\nAfter FL: {post_fl_label} ({post_fl_prob.max():.2f})")
            plt.axis('off')
        plt.tight_layout()
        plt.show()


# Start the federated client
if __name__ == '__main__':
    client = FederatedClient()
    client.show_test_samples()
    start_numpy_client(server_address=f"{server_address}:{port_number}", client=client)
    client.show_test_samples()