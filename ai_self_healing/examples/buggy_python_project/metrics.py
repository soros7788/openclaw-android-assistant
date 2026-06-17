def calculate_metrics(data_list):
    if not data_list:
        return 0
    return sum(data_list) / len(data_list)
