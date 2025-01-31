# -*- coding: utf-8 -*-
"""Project_CSE366_AI.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1V-YTjNSodpC68Q9lNtu_7HZtQMuE2dYy

#Load zip File
"""

!pip install gdown --quiet
file_id = "1IQCeGRBZPHXZPv_vuH4-YGqMAvC9YnAq"
!gdown "https://drive.google.com/uc?id={file_id}" -O Dataset.zip

!unzip -q Dataset.zip -d .

"""#Import Libraries"""

import time
import os
import pandas as pd
import numpy as np
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import cv2
import PIL
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm.notebook import tqdm
import torchvision
from torchvision import transforms, models
from torch.optim.lr_scheduler import StepLR
from transformers import ViTForImageClassification, ViTImageProcessor
from PIL import Image, ImageOps
from tabulate import tabulate
from torchvision.utils import make_grid
import platform
import psutil
import random
import glob

"""#Load Dataset"""

data_dir = "/content/Dataset"

file_paths = []
labels = []

for class_name in os.listdir(data_dir):
    class_dir = os.path.join(data_dir, class_name) # /content/Dataset/Healthy
    for image_name in os.listdir(class_dir):
        file_paths.append(os.path.join(class_dir, image_name)) # /content/Dataset/Healthy/image.jpg
        labels.append(class_name) # Healthy
df = pd.DataFrame({"file_path": file_paths, "label": labels})
df = df.sample(frac=1).reset_index(drop=True)

class_counts_train = df['label'].value_counts()

for class_name, count in class_counts_train.items():
    print(f"Class: {class_name}, Count: {count}")

plt.figure(figsize=(6, 4))
ax = class_counts_train.plot(kind='bar')
plt.xlabel('Classes')
plt.ylabel('Amount of data')
plt.xticks(rotation=360)
for i, count in enumerate(class_counts_train):
    ax.text(i, count + 5, str(count), ha='center')
plt.ylim(0, max(class_counts_train) * 1.2)
plt.show()

random_index = random.randint(1, len(df) - 1)
random_row = df.iloc[random_index]

file_path = random_row['file_path']
label = random_row['label']

image = Image.open(file_path)

size = image.size
channels = 'Grayscale' if image.mode == 'L' else 'RGB'
plt.title(f"Label: {label}\nSize: {size}\nChannels: {channels}")
plt.imshow(image, cmap='gray')
plt.axis('off')
plt.show()

!pip install torch torchvision transformers datasets matplotlib

"""# Custome Dataset Class"""

class SugarcaneDataset(Dataset):
    def __init__(self, dataframe, transform=None):
        self.dataframe = dataframe
        self.transform = transform

    def __len__(self):
        return len(self.dataframe)

    def __getitem__(self, idx):
        image_path = self.dataframe.iloc[idx]["file_path"]
        label = self.dataframe.iloc[idx]["label"]

        image = Image.open(image_path).convert("RGB")

        if self.transform:
            image = self.transform(image)

        return image, label

"""# Data Preprocessing"""

from sklearn.model_selection import train_test_split

# Split the dataset
train_df, test_df = train_test_split(df, test_size=0.2, stratify=df["label"], random_state=42)
val_df, test_df = train_test_split(test_df, test_size=0.5, stratify=test_df["label"], random_state=42)

# Define labels
label_map = {label: idx for idx, label in enumerate(train_df["label"].unique())}
train_df["label"] = train_df["label"].map(label_map)
val_df["label"] = val_df["label"].map(label_map)
test_df["label"] = test_df["label"].map(label_map)

# Load ViT image processor
processor = ViTImageProcessor.from_pretrained("google/vit-base-patch16-224-in21k")

#Transform with Data Augmentation
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomRotation(15),
    transforms.ToTensor(),
    transforms.Normalize(mean=processor.image_mean, std=processor.image_std),
])

# Create datasets with the transform
train_dataset = SugarcaneDataset(train_df, transform=transform)
val_dataset = SugarcaneDataset(val_df, transform=transform)
test_dataset = SugarcaneDataset(test_df, transform=transform)

"""# Data Loader"""

batch_size = 16

train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)

"""# Load Pretrained ViT"""

from transformers import AdamW

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Load model
model = ViTForImageClassification.from_pretrained(
    "google/vit-base-patch16-224-in21k",
    num_labels=len(label_map)
)
model.to(device)

# Define optimizer
optimizer = AdamW(model.parameters(), lr=5e-5)
criterion = torch.nn.CrossEntropyLoss()

"""# Training Model"""

train_losses = []
val_losses = []
val_accuracies = []

def train_model(model, train_loader, val_loader, epochs=10):
    for epoch in range(epochs):
        model.train()
        train_loss = 0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)

            optimizer.zero_grad()
            outputs = model(pixel_values=images).logits
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            train_loss += loss.item()

        train_losses.append(train_loss / len(train_loader))

        # Validation
        model.eval()
        val_loss = 0
        val_correct = 0
        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(pixel_values=images).logits
                loss = criterion(outputs, labels)
                val_loss += loss.item()

                predictions = outputs.argmax(dim=1)
                val_correct += (predictions == labels).sum().item()

        val_accuracy = val_correct / len(val_loader.dataset)
        val_losses.append(val_loss / len(val_loader))
        val_accuracies.append(val_accuracy)

        print(f"Epoch {epoch + 1}, Train Loss: {train_loss / len(train_loader)}, Val Loss: {val_loss / len(val_loader)}, Val Accuracy: {val_accuracy}")

    # Plot the training and validation loss/accuracy
    plt.figure(figsize=(12, 5))

    # Plot loss curves
    plt.subplot(1, 2, 1)
    plt.plot(range(epochs), train_losses, label='Training Loss')
    plt.plot(range(epochs), val_losses, label='Validation Loss')
    plt.xlabel('Epochs')
    plt.ylabel('Loss')
    plt.legend()

    # Plot accuracy curves
    plt.subplot(1, 2, 2)
    plt.plot(range(epochs), val_accuracies, label='Validation Accuracy')
    plt.xlabel('Epochs')
    plt.ylabel('Accuracy')
    plt.legend()

    plt.show()

train_model(model, train_loader, val_loader, epochs=10)

"""# Upload Image to Predict the Disease Type"""

# Import necessary libraries
import torch
from torch.utils.data import DataLoader
from torchvision import transforms
from PIL import Image
import matplotlib.pyplot as plt

# Enter Project Path
image_path =  "/content/Sugarcane Leaf(3RU).jpeg"

# Set the device for inference
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# 1. Define Image Preprocessing Function
def preprocess_image(image_path, transform=None):
    image = Image.open(image_path).convert("RGB")
    if transform:
        image = transform(image)
    return image

# 2. Define Prediction Function
def predict_disease(image_path, model, transform=None):
    image = preprocess_image(image_path, transform)
    image = image.unsqueeze(0).to(device)  # Add batch dimension and send to device

    # Make prediction
    with torch.no_grad():
        outputs = model(pixel_values=image).logits
        predictions = outputs.argmax(dim=1)

    predicted_class = predictions.item()
    class_names = list(label_map.keys())
    predicted_label = class_names[predicted_class]

    return predicted_label

# 3. Display Image and Prediction
def display_image(image_path):
    image = Image.open(image_path)
    plt.imshow(image)
    plt.axis("off")
    plt.show()

# 4. Test the Model on New Images
model.eval()  # Set the model to evaluation mode

predicted_label = predict_disease(image_path, model, transform)

# Optionally display the image and prediction result
display_image(image_path)
print(f"Predicted Disease: {predicted_label}")

"""# Testing"""

model.eval()
test_correct = 0
all_labels = []
all_preds = []

with torch.no_grad():
    for images, labels in test_loader:
        images, labels = images.to(device), labels.to(device)
        outputs = model(pixel_values=images).logits
        predictions = outputs.argmax(dim=1)

        all_labels.extend(labels.cpu().numpy())
        all_preds.extend(predictions.cpu().numpy())
        test_correct += (predictions == labels).sum().item()

test_accuracy = test_correct / len(test_loader.dataset)
print(f"Test Accuracy: {test_accuracy}")
print(classification_report(all_labels, all_preds, target_names=label_map.keys()))