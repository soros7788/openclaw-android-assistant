def calculate_metrics(data_list):
    if len(data_list) == 0:
        return 0
    return sum(data_list) / len(data_list)
