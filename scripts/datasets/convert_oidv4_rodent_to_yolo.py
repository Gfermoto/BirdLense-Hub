"""
Конвертация выгрузки Open Images (OIDv4 Toolkit) в YOLO-детекцию для грызунов.

Апстрим по умолчанию кладёт класс в каталоги ``train/Squirrel`` / ``validation/Squirrel``
(таково имя класса в Open Images); числовой id в этом скрипте — как в прежней
сборке для слияния с NABirds. В ``dataset.yaml`` метка задаётся **Rodent**,
чтобы новые обучения совпадали с каноном BirdLense Hub.
Выход по умолчанию: ``binary/rodent/`` (рядом со скриптами в ``scripts/datasets/``).
"""
import os
import shutil
import cv2
import yaml

# OIDv4 Toolkit: имена каталогов задаёт выгрузка (класс /m/071qp в Open Images).
original_train_dir = "./train/Squirrel"
original_val_dir = "./validation/Squirrel"
new_dataset_dir = "./binary/rodent"
os.makedirs(new_dataset_dir, exist_ok=True)

# Create directories for YOLO format
yolo_train_dir = os.path.join(new_dataset_dir, "train", "labels")
yolo_val_dir = os.path.join(new_dataset_dir, "val", "labels")
os.makedirs(yolo_train_dir, exist_ok=True)
os.makedirs(yolo_val_dir, exist_ok=True)

# Directories for copying images
yolo_train_img_dir = os.path.join(new_dataset_dir, "train", "images")
yolo_val_img_dir = os.path.join(new_dataset_dir, "val", "images")
os.makedirs(yolo_train_img_dir, exist_ok=True)
os.makedirs(yolo_val_img_dir, exist_ok=True)

# Class index (как в исторической сборке bird+squirrel rodent head для merge)
rodent_class_index = 1011


def process_directory(original_dir, yolo_label_dir, yolo_img_dir):
    label_dir = os.path.join(original_dir, "Label")
    for file_name in os.listdir(label_dir):
        if file_name.endswith(".txt"):
            with open(os.path.join(label_dir, file_name), "r") as f:
                content = f.readline().strip().split()
                _class_name = content[0]
                left, top, right, bottom = map(float, content[1:])

                image_file_name = file_name.replace(".txt", ".jpg")
                image_path = os.path.join(original_dir, image_file_name)
                if not os.path.exists(image_path):
                    image_file_name = file_name.replace(".txt", ".png")
                    image_path = os.path.join(original_dir, image_file_name)

                if not os.path.exists(image_path):
                    print(f"Image not found for {file_name}, skipping...")
                    continue

                image = cv2.imread(image_path)
                if image is None:
                    print(f"Failed to read image {image_path}, skipping...")
                    continue
                image_height, image_width = image.shape[:2]

                x_center = (left + right) / 2 / image_width
                y_center = (top + bottom) / 2 / image_height
                box_width = (right - left) / image_width
                box_height = (bottom - top) / image_height

                yolo_label_path = os.path.join(yolo_label_dir, file_name)
                with open(yolo_label_path, "w") as yolo_label_file:
                    yolo_label_file.write(
                        f"{rodent_class_index} {x_center} {y_center} {box_width} {box_height}\n"
                    )

                new_image_path = os.path.join(yolo_img_dir, image_file_name)
                shutil.copyfile(image_path, new_image_path)
                print(f"Processed {image_file_name} and {file_name}")


process_directory(original_train_dir, yolo_train_dir, yolo_train_img_dir)
process_directory(original_val_dir, yolo_val_dir, yolo_val_img_dir)

yolo_yaml = {
    "path": new_dataset_dir,
    "train": "train/images",
    "val": "val/images",
    "test": "",
    "names": {rodent_class_index: "Rodent"},
}

yaml_path = os.path.join(new_dataset_dir, "dataset.yaml")
with open(yaml_path, "w") as yaml_file:
    yaml.dump(yolo_yaml, yaml_file, default_flow_style=False)

print("Conversion to YOLO format completed in the new dataset directory.")
