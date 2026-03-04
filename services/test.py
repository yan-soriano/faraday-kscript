from kit_reader import load_project
data = load_project(r"C:\Users\User\Downloads\Тест.kitsp")
print(len(data["scenes"]))  # должно вывести количество сцен
print(data["scenes"][0])    # должна вывести первую сцену со всеми полями