import face_recognition


def encode_face(image_path):
    image = face_recognition.load_image_file(image_path)
    encodings = face_recognition.face_encodings(image)
    return encodings[0] if encodings else None


def match_face(unknown_encoding, known_encodings_list, tolerance=0.5):
    if not known_encodings_list:
        return None
    distances = face_recognition.face_distance(known_encodings_list, unknown_encoding)
    best_idx = int(distances.argmin())
    if distances[best_idx] <= tolerance:
        return best_idx
    return None
