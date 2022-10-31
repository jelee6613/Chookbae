from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from django.http import Http404
import datetime
from django.db import transaction
from django.shortcuts import render
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from .Serializers import CardSerializer
from .models import User, Point, Venue, Team, Match, Player, PlayerCard, Prediction, Bet, EmailCert

# Create your views here.

# 승부 예측 POST
 
class matchpredict(APIView):
    param = openapi.Schema(type=openapi.TYPE_OBJECT, required=['match_pk', 'point', 'predict'],
    properties={
        'match_pk': openapi.Schema(type=openapi.TYPE_NUMBER, description="경기 번호"),
        'point': openapi.Schema(type=openapi.TYPE_NUMBER, description="배팅 포인트"),
        'predict': openapi.Schema(type=openapi.TYPE_NUMBER, description="승부 예측"),
        })

    @transaction.atomic()
    def get_object(self,user_id, match_pk, point, predict):

        match=Match.objects.get(id=match_pk)
        user=User.objects.get(id=1)
        if(user.points<point):
            return ('보유하고 있는 포인트를 확인해 주세요.')
             
        try:
            pre=Prediction.objects.get(match_id=match_pk,user_id=1)
            return ('이미 예측을 완료한 경기입니다.')
           
        except Prediction.DoesNotExist:
            user.points-=point
            user.save()
            po=Point.objects.create(user_id=user,point=point,info='경기 결과 예측 배팅')
            pred=Prediction.objects.create(user_point=point,predict=predict,match_id=match,user_id=user)
           

        try:  
            match_num=Bet.objects.get(id=match_pk)
        except Bet.DoesNotExist:
            bet=Bet.objects.create(id=match, win=0, draw=0, lose=0)
            
        bet=Bet.objects.get(id=match_pk)
        
        if(predict==0):
            bet.win+=point
        elif(predict==1):
            bet.draw+=point
        else: 
            bet.lose+=point

        bet.save()
        
        return ('success')
            
    @swagger_auto_schema(operation_id="승부 예측", operation_description="승부 예측하기", request_body=param)
    def post(self, request, format=None):
        user_id=1
        ingredient = self.get_object(user_id,request.data['match_pk'],request.data['point'],request.data['predict'])

        #print(request.META.get('HTTP_AUTHORIZATION'))
        print(ingredient)
        if (ingredient=='success'):
            return Response(ingredient,status=status.HTTP_200_OK)
        else :
            return Response({'error' :ingredient},status=status.HTTP_400_BAD_REQUEST)
        

#승부 예측 여부 GET
class predictinfo(APIView):
    id = openapi.Parameter('id', openapi.IN_PATH, description='match_id', required=True, type=openapi.TYPE_NUMBER)
    @swagger_auto_schema(operation_id="유저의 승부 예측 여부를 조회", operation_description="제공 받은 토큰 값을 기준으로 유저를 파악하고 해당 유저가 승부 예측을 했는지 확인한다", manual_parameters=[id])
    def get(self, request, id):
        user_id=1
        try:
            predict=Prediction.objects.get(match_id=id ,user_id=user_id)
            return Response({True}, status=status.HTTP_200_OK)
        except Prediction.DoesNotExist:
            return Response({False}, status=status.HTTP_200_OK)
        except Prediction.MultipleObjectsReturned:
            return Response({False}, status=status.HTTP_400_BAD_REQUEST)


# AUTO 정산            
@transaction.atomic()
def predictcalc():
    today=datetime.datetime.now().date()
    time=datetime.datetime.now().time()
    matches= Match.objects.filter(Q(start_date=today, start_time__lte=time) | Q(start_date=today-datetime.timedelta(days=1), start_time__gt=time))
    for match in matches:
        result=0
        dang=0

        bet=Bet.objects.get(id=match.id)
        total=bet.win+bet.draw+bet.lose
        if(match.team1_score>match.team2_score and bet.win!=0):
            result=0
            dang=total/bet.win
        elif(match.team1_score==match.team2_score and bet.draw!=0):
            result=1
            dang=total/bet.draw
        elif(match.team1_score<match.team2_score and bet.lose!=0):
            result=2
            dang=total/bet.lose

        predictinfo=Prediction.objects.filter(match_id=match.id,predict=result)

        for pre in predictinfo:
            user=User.objects.get(id=pre.user_id.id)
            user.points+=(dang*pre.user_point)
            user.save()
            po=Point.objects.create(user_id=user,point=dang*pre.user_point,info='경기 예측 성공')

#선수 뽑기 POST
class card(APIView):
    param = openapi.Schema(type=openapi.TYPE_OBJECT, required=['team_id', 'gacha_count', 'point'],
    properties={
        'team_id': openapi.Schema(type=openapi.TYPE_NUMBER, description="국가 번호"),
        'gacha_count': openapi.Schema(type=openapi.TYPE_NUMBER, description="가챠 횟수"),
        'point': openapi.Schema(type=openapi.TYPE_NUMBER, description="소모 포인트"),
        })

    @transaction.atomic()
    def get_object(self, user_id, team_id,gacha_count,point):
        c_list=[]
        user=User.objects.get(id=user_id)

        if(user.points<point):
            return ('보유하고 있는 포인트를 확인해 주세요.')

        for i in range(gacha_count):
            if(team_id > 0):
                card=Player.objects.filter(team_id=team_id).order_by('?').first()
            else :
                card=Player.objects.order_by('?').first()     

            new_card=PlayerCard.objects.create(player_id=card, user_id=user)
            serializer = CardSerializer(card)
            c_list.append(serializer.data)
        user.points-=point
        user.save()
        po=Point.objects.create(user_id=user,point=point,info='선수 뽑기')

        return (c_list)

    @swagger_auto_schema(operation_id="카드 뽑기", operation_description="새로운 선수카드 뽑기", request_body=param)
    def post(self, request, format=None):
        user_id=1
        gacha=self.get_object(user_id,request.data['team_id'],request.data['gacha_count'],request.data['point'])

        if(gacha=='보유하고 있는 포인트를 확인해 주세요.'):
            return Response({'error' :gacha},status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(gacha,status=status.HTTP_200_OK)

    @swagger_auto_schema(operation_id="유저의 보유하고 있는 카드 확인", operation_description="해당 유저가 보유하고 있는 모든 카드의 정보를 가져온다.")
    def get(self, request):
        c_list=[]
        country = request.GET.get('country', None)
        team=Team.objects.get(country=country)
        user_id=1

        card=PlayerCard.objects.filter(user_id=user_id)

        for i in card:
            C=Player.objects.get(id=i.player_id.id)
            if team is not None:
                if(C.team_id != team):
                    continue
            serializer = CardSerializer(C)
            c_list.append(serializer.data)
        
        return Response(c_list)    

#선수 합성 POST
class combine(APIView):
    param = openapi.Schema(type=openapi.TYPE_OBJECT, required=['player_card_id1', 'player_card_id2'],
    properties={
        'player_card_id1': openapi.Schema(type=openapi.TYPE_NUMBER, description="첫 번째 선수 카드"),
        'player_card_id2': openapi.Schema(type=openapi.TYPE_NUMBER, description="두 번째 선수 카드"),
        })


    @transaction.atomic()
    def get_object(self, user_id, card1, card2):
        user=User.objects.get(id=user_id)
        first=PlayerCard.objects.get(id=card1)
        second=PlayerCard.objects.get(id=card2)
        team=-1

        if(user_id != first.user_id.id or user_id != second.user_id.id):
            return ('보유하고 있지 않은 선수카드입니다.')
        
        if(first.player_id.team_id == second.player_id.team_id):
            team=first.player_id.team_id.id
        

        if(team>0):
            card=Player.objects.filter(Q(team_id=team) & ~Q(id=first.player_id.id) & ~Q(id=second.player_id.id)).order_by('?').first()
        else :
            card=Player.objects.filter((~Q(id=first.player_id.id) & ~Q(id=second.player_id.id))).order_by('?').first()     

        if card is None:
            return ('뽑을 선수가 없습니다.')

        first.delete()
        second.delete()
        new_card=PlayerCard.objects.create(player_id=card, user_id=user)
        serializer = CardSerializer(card)
        return (serializer.data)

    @swagger_auto_schema(operation_id="카드 합성", operation_description="기존의 선수 합성하여 새 선수 뽑기", request_body=param)
    def post(self, request, format=None):
        user_id=1
        comb=self.get_object(user_id,request.data['player_card_id1'],request.data['player_card_id2'])

        if(comb=='보유하고 있지 않은 선수카드입니다.' or comb=='뽑을 선수가 없습니다.'):
            return Response({'error' :comb},status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(comb,status=status.HTTP_200_OK)




