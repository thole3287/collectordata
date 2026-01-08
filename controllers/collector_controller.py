from flask import jsonify
import services.auto_collector_service as auto_collector_service

def start_auto_collector():
    result = auto_collector_service.auto_collector.start()
    return jsonify(result)

def stop_auto_collector():
    result = auto_collector_service.auto_collector.stop()
    return jsonify(result)

def get_auto_collector_status():
    result = auto_collector_service.auto_collector.get_status()
    return jsonify(result)
