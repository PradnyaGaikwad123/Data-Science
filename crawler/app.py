from collections import Counter
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template,jsonify, request
import os
import psycopg2
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from io import BytesIO
import base64
import pandas as pd
import logging


app = Flask(__name__)

# Load environment variables from the .env file
load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')

logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                    level=logging.DEBUG,
                    datefmt='%Y-%m-%d %H:%M:%S')

try:        
    # Connect to Database
    db_connection = psycopg2.connect(dsn=DATABASE_URL)
    cur = db_connection.cursor()
except Exception as e:
    raise Exception('Not able to connect to Database')


# FRONTEND APIs and functions

# Dashboard
@app.route('/')
def index():
    count_data = get_counts()
    return render_template('dashboard.html', count_data=count_data)

# Frequency Analysis
@app.route('/frequency_analysis')
def frequency_analysis():
    return render_template('frequency_analysis.html')

# Word Popularity
@app.route('/word_popularity')
def page2():
    return render_template('word_popularity.html')

# Toxicity
@app.route('/toxicity')
def page3():
    return render_template('toxicity.html')


# Top subreddits by post count
@app.route('/top_subreddits_post_count')
def top_subreddits_post_count():
    n = int(request.args.get('n', 10)) # Set 10 as default value
    from_date = request.args.get('from_date', '2023-11-01') # Default From Date is 01 Nov 2023
    to_date = request.args.get('to_date', datetime.today().strftime('%Y-%m-%d')) # Default To Date is Current Date
    sql_query = f"SELECT subreddit, COUNT(*) as post_count FROM reddit_posts WHERE subreddit != 'politics' AND created >= '{from_date}' AND created <= '{to_date}' GROUP BY subreddit ORDER BY post_count DESC LIMIT {n}"
    cur.execute(sql_query)
    result = cur.fetchall()
    subreddits = [i[0] for i in result]
    post_counts = [i[1] for i in result]
    return jsonify(subreddits=subreddits, post_counts=post_counts)

# Top subreddits by comment count
@app.route('/top_subreddits_comment_count')
def top_subreddits_comment_count():
    n = int(request.args.get('n', 10))  # Set 10 as default value
    from_date = request.args.get('from_date', '2023-11-01') # Default From Date is 01 Nov 2023
    to_date = request.args.get('to_date', datetime.today().strftime('%Y-%m-%d')) # Default To Date is Current Date
    sql_query = f"SELECT subreddit, COUNT(*) as comment_count FROM reddit_comments WHERE subreddit != 'politics' AND created >= '{from_date}' AND created <= '{to_date}' GROUP BY subreddit ORDER BY comment_count DESC LIMIT {n}"
    cur.execute(sql_query)
    result = cur.fetchall()
    subreddits = [i[0] for i in result]
    comment_counts = [i[1] for i in result]
    return jsonify(subreddits=subreddits, comment_counts=comment_counts)

# Top hashtags by post count for Tumblr
@app.route('/top_tumblr_hashtags_post_count')
def top_tumblr_hashtags_post_count():
    n = int(request.args.get('n', 10))  # Set 10 as default value
    from_date = request.args.get('from_date', '2023-11-01') # Default To Date is 01 Nov 2023
    to_date = request.args.get('to_date', datetime.today().strftime('%Y-%m-%d')) # Default To Date is Current Date
    sql_query = f"SELECT post_hashtag, COUNT(*) as post_count FROM tumblr_posts WHERE post_hashtag != 'politics' AND post_date >= '{from_date}' AND post_date <= '{to_date}' GROUP BY post_hashtag ORDER BY post_count DESC LIMIT {n}"
    cur.execute(sql_query)
    result = cur.fetchall()
    hashtags = [i[0] for i in result]
    post_counts = [i[1] for i in result]
    return jsonify(hashtags=hashtags, post_counts=post_counts)

# Top hashtags by replies count for Tumblr
@app.route('/top_tumblr_hashtags_replies_count')
def top_tumblr_hashtags_replies_count():
    n = int(request.args.get('n', 10))  # Default to 10 if 'n' is not provided
    from_date = request.args.get('from_date', '2023-11-01') # Default To Date is 01 Nov 2023
    to_date = request.args.get('to_date', datetime.today().strftime('%Y-%m-%d')) # Default To Date is Current Date
    sql_query = f"SELECT hashtag, COUNT(*) as replies_count FROM tumblr_post_replies WHERE hashtag != 'politics' GROUP BY hashtag ORDER BY replies_count DESC LIMIT {n}"
    cur.execute(sql_query)
    result = cur.fetchall()
    hashtags = [i[0] for i in result]
    replies_counts = [i[1] for i in result]
    return jsonify(hashtags=hashtags, replies_counts=replies_counts)

@app.route('/top_tumblr_keywords')
def top_tumblr_keywords():
    n = int(request.args.get('n', 10))  # Default to 10 if 'n' is not provided
    from_date = request.args.get('from_date', '2023-11-01')  # Default From Date is 01 Nov 2023
    to_date = request.args.get('to_date', datetime.today().strftime('%Y-%m-%d'))  # Default To Date is Current Date

    # sql_query = f"SELECT post_summary FROM tumblr_posts WHERE post_hashtag != 'politics' AND post_date >= '{from_date}' AND post_date <= '{to_date}' GROUP BY post_summary LIMIT {n}"
    sql_query = f"SELECT post_summary FROM tumblr_posts WHERE post_hashtag != 'politics' AND post_date >= '{from_date}' AND post_date <= '{to_date}' LIMIT {n}"
    cur.execute(sql_query)
    
    posts = []
    replies = []

    try:
        data = cur.fetchall()
        posts = [item[0] for item in data]
    except Exception as e:
        logging.error('Error fetching data. Exception: {e}')
    

    sql_query = "SELECT reply_text FROM tumblr_post_replies"
    cur.execute(sql_query)
    
    try:
        data = cur.fetchall()
        replies = [item[0] for item in data]
    except Exception as e:
        logging.error('Error fetching data. Exception: {e}')
    

    all_tumblr_texts = posts + replies
    keyword_counts = perform_keyword_occurrences_analysis(all_tumblr_texts)
    sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
    top_keywords = [keyword[0] for keyword in sorted_keywords[:n]]
    top_keyword_counts = [keyword[1] for keyword in sorted_keywords[:n]]

    return jsonify(keywords=top_keywords, keyword_counts=top_keyword_counts)

@app.route('/wordcloud_tumblr')
def wordcloud_tumblr():
    posts = []
    replies = []
    
    sql_query = "SELECT post_summary FROM tumblr_posts "
    cur.execute(sql_query)
    try:
        data = cur.fetchall()
        posts = [item[0] for item in data]
    except Exception as e:
        logging.error('Error fetching data. Exception: {e}')

    sql_query = "SELECT reply_text FROM tumblr_post_replies"
    cur.execute(sql_query)
    try:
        data = cur.fetchall()
        replies = [item[0] for item in data]
    except Exception as e:
        logging.error('Error fetching data. Exception: {e}')

    all_tumblr_text = posts + replies
    keyword_counts = perform_keyword_occurrences_analysis(all_tumblr_text)
    wordcloud = WordCloud(width=1300, height=500, background_color='white').generate_from_frequencies(keyword_counts)
    image_stream = BytesIO()
    wordcloud.to_image().save(image_stream, format='PNG')
    image_stream.seek(0)
    encoded_image = base64.b64encode(image_stream.getvalue()).decode('utf-8')
    label_html = '<h2> <i class="fab fa-tumblr" style="font-size: 1em; margin-right: 10px; color: navy;"></i> Word Cloud for Tumblr</h2>'

    return f'{label_html}<img src="data:image/png;base64,{encoded_image}" alt="Word Cloud" style="border: 2px solid #000;">'

@app.route('/wordcloud_reddit')
def wordcloud_reddit():
    posts = []
    replies = []
    
    sql_query = "SELECT selftext FROM reddit_posts"
    cur.execute(sql_query)
    try:
        data = cur.fetchall()
        posts = [item[0] for item in data]
    except Exception as e:
        logging.error('Error fetching data. Exception: {e}')

    sql_query = "SELECT body FROM reddit_comments"
    cur.execute(sql_query)
    try:
        data = cur.fetchall()
        replies = [item[0] for item in data]
    except Exception as e:
        logging.error('Error fetching data. Exception: {e}')

    # posts = fetch_data_from_database('reddit_posts', 'selftext')
    # comments = fetch_data_from_database('reddit_comments', 'body')
    # all_reddit_texts = posts + comments
    # print(f'Posts+replies fetched: ', all_reddit_texts)

    all_tumblr_text = posts + replies
    keyword_counts = perform_keyword_occurrences_analysis(all_tumblr_text)
    wordcloud = WordCloud(width=1300, height=500, background_color='white').generate_from_frequencies(keyword_counts)
    image_stream = BytesIO()
    wordcloud.to_image().save(image_stream, format='PNG')
    image_stream.seek(0)
    encoded_image = base64.b64encode(image_stream.getvalue()).decode('utf-8')
    label_html = '<h2> <i class="bi bi-reddit text-danger" style="font-size: 1em; margin-right: 10px;"></i> Word Cloud for Reddit</h2>'

    return f'{label_html}<img src="data:image/png;base64,{encoded_image}" alt="Word Cloud" style="border: 2px solid #000;">'

@app.route('/top_reddit_keywords')
def top_reddit_keywords():
    n = int(request.args.get('n', 10))  # Default to 10 if 'n' is not provided
    from_date = request.args.get('from_date', '2023-11-01')  # Default From Date is 01 Nov 2023
    to_date = request.args.get('to_date', datetime.today().strftime('%Y-%m-%d'))  # Default To Date is Current Date

    posts = []
    replies = []
    
    sql_query = f"SELECT selftext FROM reddit_posts WHERE subreddit != 'politics' AND created >= '{from_date}' AND created <= '{to_date}'"
    cur.execute(sql_query)
    try:
        data = cur.fetchall()
        posts = [item[0] for item in data]
    except Exception as e:
        logging.error('Error fetching data. Exception: {e}')

    sql_query = "SELECT body FROM reddit_comments"
    cur.execute(sql_query)
    try:
        data = cur.fetchall()
        replies = [item[0] for item in data]
    except Exception as e:
        logging.error('Error fetching data. Exception: {e}')

    all_tumblr_texts = posts + replies
    keyword_counts = perform_keyword_occurrences_analysis(all_tumblr_texts)
    sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
    top_keywords = [keyword[0] for keyword in sorted_keywords[:n]]
    top_keyword_counts = [keyword[1] for keyword in sorted_keywords[:n]]

    return jsonify(keywords=top_keywords, keyword_counts=top_keyword_counts)

# Top Subreddits with Maximum Toxic Comments
@app.route('/get_toxic_subreddits_plot_data')
def get_toxic_subreddits_plot_data():
    n = int(request.args.get('n', 10)) # Set 10 as default value
    from_date = request.args.get('from_date', '2023-11-01') # Default From Date is 01 Nov 2023
    to_date = request.args.get('to_date', datetime.today().strftime('%Y-%m-%d')) # Default To Date is Current Date
    sql_query = f"SELECT subreddit, COUNT(*) as number_of_toxic_comments FROM reddit_comments WHERE mhs_toxicity_class = 'flag' AND subreddit != 'politics' AND created >= '{from_date}' AND created <= '{to_date}' GROUP BY subreddit ORDER BY number_of_toxic_comments DESC LIMIT {n}"
    cur.execute(sql_query)
    result = cur.fetchall()
    subreddits = [i[0] for i in result]
    number_of_toxic_comments = [i[1] for i in result]
    return jsonify(subreddits=subreddits, number_of_toxic_comments=number_of_toxic_comments)

@app.route('/get_toxic_trends_plot_data')
def get_toxic_trends_plot_data():
    n = int(request.args.get('n', 10)) # Set 10 as default value
    from_date = request.args.get('from_date', '2023-11-01') # Default From Date is 01 Nov 2023
    to_date = request.args.get('to_date', datetime.today().strftime('%Y-%m-%d')) # Default To Date is Current Date

    sql_query = f"SELECT subreddit, COUNT(*) as number_of_toxic_comments FROM reddit_comments WHERE mhs_toxicity_class = 'flag' AND subreddit != 'politics' GROUP BY subreddit ORDER BY number_of_toxic_comments DESC LIMIT {n}"
    cur.execute(sql_query)
    top_10_most_toxic_subreddits = cur.fetchall()
    subreddits = [i[0] for i in top_10_most_toxic_subreddits]

    sql_query = "SELECT subreddit, DATE(created) AS comment_date, COUNT(*) AS number_of_toxic_comments FROM reddit_comments WHERE mhs_toxicity_class = 'flag' AND subreddit IN %s AND created >= %s AND created <= %s GROUP BY subreddit, comment_date ORDER BY subreddit, comment_date"
    cur.execute(sql_query, (tuple(subreddits), from_date, to_date))
    result = cur.fetchall()
    df_trend = pd.DataFrame(result, columns=['subreddit', 'comment_date', 'number_of_toxic_comments'])
    all_dates = pd.date_range(start=min(df_trend['comment_date']), end=max(df_trend['comment_date']), freq='D')
    response_data = {
        'subreddits': subreddits,
        'dates': all_dates.strftime('%Y-%m-%d').tolist(), 
        'toxic_comments': [],
    }
    for subreddit_trend in subreddits:
        subreddit_data_trend = df_trend[df_trend['subreddit'] == subreddit_trend]
        subreddit_data_trend = subreddit_data_trend.groupby('comment_date').sum()  
        subreddit_data_trend = subreddit_data_trend.reindex(all_dates, fill_value=0)  
        response_data['toxic_comments'].append(subreddit_data_trend['number_of_toxic_comments'].tolist())

    return jsonify(response_data)

# HELPER FUNCTIONS 

# Function to get total post and comment counts from DB
def get_counts():
    # Get total posts from reddit 
    sql_query = 'SELECT COUNT(*) from reddit_posts'
    cur.execute(sql_query)
    reddit_posts_count = cur.fetchone()[0]

    # Get total comments from reddit 
    sql_query = 'SELECT COUNT(*) from reddit_comments'
    cur.execute(sql_query)
    reddit_comments_count = cur.fetchone()[0]

    # Get total posts from tumblr
    sql_query = 'SELECT COUNT(*) from tumblr_posts'
    cur.execute(sql_query)
    tumblr_posts_count = cur.fetchone()[0]

    # Get total comments from tumblr
    sql_query = 'SELECT COUNT(*) from tumblr_post_replies'
    cur.execute(sql_query)
    tumblr_comments_count = cur.fetchone()[0]

    return [ reddit_posts_count, reddit_comments_count, tumblr_posts_count, tumblr_comments_count]
   
def preprocess_text(text):
        return text.lower()

def count_keyword_occurrences(texts, keywords):
        keyword_counts = Counter()
        combined_text = ' '.join(map(str, texts))
        processed_text = preprocess_text(combined_text)
        # Count occurrences of each keyword(hashtag)
        for keyword in keywords:
            keyword_counts[keyword] = processed_text.count(keyword)
        return keyword_counts

def perform_keyword_occurrences_analysis(texts):
        # Define the list of keywords
        general_trending_technology_topics = ['tech', 'code', 'coding', 'programming', 'jobs', 'DevOps',
        'technology', 'developer', 'software engineering', 'computer science', 'hacking', 'software', 'digital', 'IT', 'android']

        languages = ['python', 'JavaScript', 'Java', 'cpp', 'csharp', 'cprogram', 'rust', 'php', 'typescript', 'sql', 'r language', 'matlab']

        domains = ['data science', 'machine learning', 'Artificial Intelligence', 'Deep Learning', 'web development', 'web design', 'app developers', 'frontend', 
         'cybersecurity', 'computer networks', 'game development', 'augmented reality', 'virtual reality','blockchain', 'big data', 'chatgpt', 'data analytics']
        
        frameworks = ['reactjs', 'nodejs', 'azure','djangodevelopers','flutterdev','aws','kubernetes','flask','docker']

        all_keywords = (
            general_trending_technology_topics +
            languages +
            domains +
            frameworks
        )

        keyword_counts = count_keyword_occurrences(texts, all_keywords)
        sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)

        # Print the top 10 keywords with the maximum occurrences
        # print("Top 10 Hashtags with the maximum occurrences:")
        # for keyword, count in sorted_keywords[:10]:
        #     print(f'Hashtag: {keyword}, Occurrences: {count}')

        return keyword_counts

if __name__ == '__main__':
    app.run(debug=False)
