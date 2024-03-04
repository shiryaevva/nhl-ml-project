# Предсказательные модели прогнозирования результата матча Национальной Хоккейной Лиги

## Постановка задачи
**Авторы работы:**
- Галанов Максим (telegram: [@maxglnv](https://t.me/maxglnv))
- Ширяева Виктория (telegram: [@shiryaevva](https://t.me/shiryaevva))

**Научный руководитель:**
- Гаврилова Елизавета (telegram: [@lizvladii](https://t.me/lizvladii))

**Цель проекта:**
В рамках данного проекта планируется создать аналитический сервис, с помощью которого можно будет получить статистику команд и игроков по резултатам завершенных игр, а так прогноз результатов предстоящих игр. 


## План выполнения
**1. Сбор данных из API NHL:**
   - Определение необходимых данных для анализа
   - Написание скриптов для регулярного сбора данных
   - Тестирование и отладка сбора данных
   - Ориентировочная дата выполнения: 2024-03-10

**2. Создание хранилища данных (DWH):**
   - Проектирование структуры базы данных
   - Развертывание DWH
   - Наполнение данными из API NHL
   - Ориентировочная дата выполнения: 2024-03-17

**3. Подготовка данных для анализа:**
   - Создание витрин данных для ML и DL моделей
   - Ориентировочная дата выполнения: 2024-03-24

**4. Исследование ML и DL подходов:**
   - Выбор целевых пременных
   - Выбор алгоритмов
   - Обучение моделей на подготовленных данных
   - Оценка качества моделей
   - Ориентировочная дата выполнения: 2024-04-14

**5. Создание дашбордов:**
   - Выбор инструментов для создания дашбордов
   - Визуализация результатов анализа данных
   - Ориентировочная дата выполнения: 2024-04-21

**6. Разработка телеграм бота:**
   - Проектирование интерфейса бота
   - Написание скриптов для взаимодействия с пользователем
   - Тестирование и отладка бота
   - Ориентировочная дата выполнения: 2024-05-05

**7. Итоговая сборка и документация:**
   - Итоговая интеграция всех компонентов проекта
   - Написание документации к проекту
   - Подготовка презентации для защиты ВКР
   - Ориентировочная дата выполнения: 2024-05-26

## Описание данных
Для анализа мы будем использовать данные из API NHL, включающие информацию о матчах, командах, игроках, статистике и другие характеристики.
