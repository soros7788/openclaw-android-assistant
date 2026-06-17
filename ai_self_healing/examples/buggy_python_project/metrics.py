def calculate_metrics(data_list):
    if len(data_list) == 0:
        return None
    result = sum(data_list) / len(data_list)
    return result
