import numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score

print("Начинаем создание и обучение простой модели линейной регрессии...")

np.random.seed(0)
X = 2 * np.random.rand(100, 1)
y = 4 + 3 * X + np.random.rand(100, 1)

print("Сгенерировано {len(X)} точек данных.")

plt.figure(figsize=(10, 6))
plt.scatter(X, y, color='blue', label='Сгенерированные данные (X, y)')
plt.title('Сгенерированные данные для линейной регрессии')
plt.xlabel('Значение X')
plt.ylabel('Значение Y')
plt.legend()
plt.grid(True)
plt.show()

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

print(f"Данные разделены: {len(X_train)} точек для обучения, {len(X_test)} точек для тестирования.")

model = LinearRegression()
model.fit(X_train, y_train)

print("Модель успешно обучена!")
print(f"Найденный коэффициент (m): {model.coef_[0][0]:.2f}")
print(f"Найденное смещение (b): {model.intercept_[0]:.2f}")

y_pred = model.predict(X_test)

plt.figure(figsize=(10, 6))
plt.scatter(X_test, y_test, color='blue', label='Реальные тестовые задания')
plt.plot(X_test, y_pred, color='red', linewidth=3, label='Предсказанная линейная регрессия')
plt.title('Результаты линейной регрессии')
plt.xlabel('Значение X')
plt.ylabel('Значение Y')
plt.legend()
plt.grid(True)
plt.show()

mse = mean_squared_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

print(f"\nОценка модели: ")
print(f"Среднеквадратичная ошибка (MSE): {mse:.2f}")
print(f"Коэффициент детерминация (R^2): {r2:.2f}")

print("\nДемонстрация предсказания для нового значения X:")
new_X = np.array([1.5]).reshape(-1, 1)
predicted_y = model.predict(new_X)
print(f"Для X =  {new_X[0][0]:.2f}, предсказанное Y = {predicted_y[0][0]:.2f}")

print(f"Простая модель машинного обучения успешно создана и продемонстрирована!")
