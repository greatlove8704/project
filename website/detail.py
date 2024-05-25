import logging
from flask import Blueprint, render_template, request
from dotenv import load_dotenv
from os import environ
import requests
import pandas as pd

# Load environment variables
load_dotenv()
api_key = environ.get('API_KEY')

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s:%(message)s')

# Load movie data
movie_ids = pd.read_parquet('website/static/id_title.parquet', columns=['id'])
similarity_df = pd.read_parquet('website/static/similarity_df.parquet')

def recommend(id, limit=8):
    logging.debug(f'Start recommendation for movie_id: {id}')
    movie_index = movie_ids[movie_ids['id'] == int(id)].index[0]
    distances = similarity_df.iloc[movie_index].values
    movies_list = sorted(
        list(enumerate(distances)), reverse=True, key=lambda x: x[1]
    )[1:limit+1]
    logging.debug(f'Recommendation list: {movies_list}')
    return [movie_ids.iloc[m[0]].id for m in movies_list]

def get_data(movie_id):
    logging.debug(f'Start fetching data for movie_id: {movie_id}')
    try:
        logging.debug(f'API Key: {api_key}')
        meta_url = f'http://api.themoviedb.org/3/movie/{movie_id}?api_key={api_key}&language=en-US'
        meta_resp = requests.get(meta_url)
        if meta_resp.status_code == 401:
            logging.error('Unauthorized access - check your API key')
            return {}
        meta_resp = meta_resp.json()
        logging.debug(f'Meta response: {meta_resp}')
        
        data = {
            'poster_path': 'https://image.tmdb.org/t/p/w500'+meta_resp.get('poster_path'),
            'title': meta_resp.get('title'),
            'release_date': meta_resp.get('release_date'),
            'genres': [g['name'] for g in meta_resp.get('genres')],
            'popularity': f"{float(meta_resp.get('popularity')):.1f}",
            'overview': meta_resp.get('overview')
        }

        credits_url = f'https://api.themoviedb.org/3/movie/{movie_id}/credits?api_key={api_key}&language=en-US'
        credits_resp = requests.get(credits_url).json()
        logging.debug(f'Credits response: {credits_resp}')

        data['directors'] = [
            c['name']
            for c in credits_resp.get('crew') if c['job'] == 'Director'
        ]

        actors = sorted(
            credits_resp.get('cast'), key=lambda x: x['popularity']
        )[::-1][:6]

        data['cast'] = [
            {'name': c['name'], 'profile_path': 'https://image.tmdb.org/t/p/w500'+c['profile_path']} for c in actors
        ]

        trailers_url = f'https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={api_key}&language=en-US'
        trailers_resp = requests.get(trailers_url).json()
        logging.debug(f'Trailers response: {trailers_resp}')
        trailers = [
            {'name': video['name'], 'key': video['key']}
            for video in trailers_resp.get('results', [])
            if video['site'].lower() == 'youtube' and video['type'].lower() == 'trailer'
        ]

        data['trailers'] = trailers

        recommendations = recommend(movie_id)
        
        data['recommendation_data'] = []

        for id in recommendations:
            recom_url = f'http://api.themoviedb.org/3/movie/{id}?api_key={api_key}&language=en-US'
            recom_resp = requests.get(recom_url).json()
            logging.debug(f'Recommendation response: {recom_resp}')

            data['recommendation_data'].append({
                'id': id,
                'title': recom_resp.get('title'),
                'poster_path': 'https://image.tmdb.org/t/p/w500'+recom_resp.get('poster_path'),
                'year': recom_resp.get('release_date').split('-')[0],
                'language': recom_resp.get('original_language').capitalize(),
                'genres': [g['name'] for g in recom_resp.get('genres')]
            })
        
        logging.debug(f'Finished fetching data for movie_id: {movie_id}')
        return data
    except Exception as e:
        logging.error(f'Error fetching data: {e}')
        return {}

detail = Blueprint('detail', __name__)

@detail.route('/detail', methods=['GET'])
def home():
    return render_template('placeholder_detail.html', id=request.args.get('id'))

@detail.route('/get_detail_data', methods=['GET'])
def get_detail_html_data():
    movie_id = request.args.get('id')
    logging.debug(f'Request received for movie_id: {movie_id}')
    data = get_data(movie_id)
    logging.debug(f'Render data for movie_id: {movie_id}')
    return {'data': render_template('detail.html', data=data)}
