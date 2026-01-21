"""
Log Analyzer Module

ログファイルの自動解析と統計情報生成
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import Counter, defaultdict

from config.config import settings
from src.core.logger import logger


class LogAnalyzer:
    """
    ログ解析クラス
    
    機能:
    1. ログファイルのパース
    2. 統計情報の生成
    3. エラーパターンの検出
    4. 異常検知
    """
    
    # 正規表現パターン
    LOG_LEVEL_PATTERN = r'\[(DEBUG|INFO|WARNING|ERROR|CRITICAL)\]'
    TIMESTAMP_PATTERN = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})'
    ACCOUNT_ID_PATTERN = r'account[=:]([a-zA-Z0-9-]+)'
    
    def __init__(self, log_file_path: Path):
        """
        初期化
        
        Args:
            log_file_path: ログファイルパス
        """
        self.log_file_path = Path(log_file_path)
        self.parsed_logs: List[Dict[str, Any]] = []
    
    def parse_logs(self):
        """ログファイルをパース"""
        if not self.log_file_path.exists():
            logger.warning(f"Log file not found: {self.log_file_path}")
            return
        
        self.parsed_logs = []
        
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    log_entry = self._parse_line(line)
                    if log_entry:
                        self.parsed_logs.append(log_entry)
            
            logger.info(f"Parsed {len(self.parsed_logs)} log entries")
            
        except Exception as e:
            logger.error(f"Failed to parse log file: {e}")
    
    def _parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        """1行のログをパース"""
        log_entry = {
            'timestamp': None,
            'level': None,
            'message': line.strip(),
            'account_id': None,
        }
        
        # タイムスタンプ抽出
        timestamp_match = re.search(self.TIMESTAMP_PATTERN, line)
        if timestamp_match:
            try:
                log_entry['timestamp'] = datetime.strptime(
                    timestamp_match.group(1),
                    "%Y-%m-%d %H:%M:%S"
                )
            except ValueError:
                pass
        
        # ログレベル抽出
        level_match = re.search(self.LOG_LEVEL_PATTERN, line)
        if level_match:
            log_entry['level'] = level_match.group(1)
        
        # アカウントID抽出
        account_match = re.search(self.ACCOUNT_ID_PATTERN, line)
        if account_match:
            log_entry['account_id'] = account_match.group(1)
        
        return log_entry if log_entry['level'] else None
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        ログ統計を取得
        
        Returns:
            Dict[str, Any]: 統計情報
        """
        if not self.parsed_logs:
            self.parse_logs()
        
        # レベル別カウント
        level_counts = Counter(log['level'] for log in self.parsed_logs)
        
        # アカウント別カウント
        account_counts = Counter(
            log['account_id'] for log in self.parsed_logs 
            if log['account_id']
        )
        
        # 時間帯別カウント
        hourly_counts = defaultdict(int)
        for log in self.parsed_logs:
            if log['timestamp']:
                hour = log['timestamp'].hour
                hourly_counts[hour] += 1
        
        return {
            'total_logs': len(self.parsed_logs),
            'by_level': dict(level_counts),
            'by_account': dict(account_counts.most_common(10)),
            'by_hour': dict(sorted(hourly_counts.items())),
            'error_rate': level_counts.get('ERROR', 0) / len(self.parsed_logs) if self.parsed_logs else 0
        }
    
    def get_error_summary(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        エラーログのサマリーを取得
        
        Args:
            limit: 取得件数
        
        Returns:
            List[Dict[str, Any]]: エラーログリスト
        """
        if not self.parsed_logs:
            self.parse_logs()
        
        errors = [
            log for log in self.parsed_logs
            if log['level'] in ['ERROR', 'CRITICAL']
        ]
        
        # タイムスタンプでソート（新しい順）
        errors.sort(key=lambda x: x['timestamp'] or datetime.min, reverse=True)
        
        return errors[:limit]
    
    def detect_anomalies(self) -> Dict[str, Any]:
        """
        異常パターンを検出
        
        Returns:
            Dict[str, Any]: 異常検知結果
        """
        if not self.parsed_logs:
            self.parse_logs()
        
        anomalies = {
            'high_error_rate_accounts': [],
            'repeated_errors': [],
            'timeout_errors': 0,
            'login_failures': 0
        }
        
        # アカウント別エラー率
        account_stats = defaultdict(lambda: {'total': 0, 'errors': 0})
        for log in self.parsed_logs:
            if log['account_id']:
                account_stats[log['account_id']]['total'] += 1
                if log['level'] in ['ERROR', 'CRITICAL']:
                    account_stats[log['account_id']]['errors'] += 1
        
        # エラー率50%以上のアカウント
        for account_id, stats in account_stats.items():
            if stats['total'] >= 5:
                error_rate = stats['errors'] / stats['total']
                if error_rate >= 0.5:
                    anomalies['high_error_rate_accounts'].append({
                        'account_id': account_id,
                        'error_rate': error_rate,
                        'total_logs': stats['total'],
                        'error_count': stats['errors']
                    })
        
        # 繰り返しエラー
        error_messages = [
            log['message'] for log in self.parsed_logs
            if log['level'] in ['ERROR', 'CRITICAL']
        ]
        error_counter = Counter(error_messages)
        
        for message, count in error_counter.most_common(5):
            if count >= 3:
                anomalies['repeated_errors'].append({
                    'message': message[:200],
                    'count': count
                })
        
        # タイムアウトエラー
        anomalies['timeout_errors'] = sum(
            1 for log in self.parsed_logs
            if 'timeout' in log['message'].lower()
        )
        
        # ログイン失敗
        anomalies['login_failures'] = sum(
            1 for log in self.parsed_logs
            if 'login' in log['message'].lower() 
            and log['level'] in ['ERROR', 'CRITICAL']
        )
        
        return anomalies
    
    def export_summary(self, output_path: str):
        """解析結果をJSONファイルにエクスポート"""
        summary = {
            'analysis_date': datetime.utcnow().isoformat(),
            'log_file': str(self.log_file_path),
            'statistics': self.get_statistics(),
            'errors': self.get_error_summary(50),
            'anomalies': self.detect_anomalies()
        }
        
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"Exported log analysis to {output_path}")


def analyze_latest_log() -> Dict[str, Any]:
    """
    最新のログファイルを解析
    
    Returns:
        Dict[str, Any]: 解析結果
    """
    date = datetime.now().strftime("%Y-%m-%d")
    log_file = settings.LOG_DIR / f"automation_{date}.log"
    
    if not log_file.exists():
        logger.warning(f"Log file not found: {log_file}")
        return {}
    
    analyzer = LogAnalyzer(log_file)
    return analyzer.get_statistics()

