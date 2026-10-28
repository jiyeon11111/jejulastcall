function makeLastcallSurvey() {
  // ▼ 이 세 줄만 팀에 맞게 고치기
  var PRIZE = '스타벅스 아메리카노 기프티콘';
  var WINNERS = 5;
  var DRAW_DATE = '11월 3일';
  // ▲
  var APP = 'https://jejulastcall.vercel.app/?now=11:00';
  var form = FormApp.create('제주 라스트콜 베타 설문 (1분)');
  form.setDescription(
    '제주 라스트콜 베타를 써 주셔서 고마워요! 1분이면 끝나요.\n' +
    '응답해 주신 분 중 ' + WINNERS + '명을 추첨해 ' + PRIZE + '을 보내 드려요. (' + DRAW_DATE + ' 발송)\n' +
    '앱을 아직 안 써 봤다면 먼저 써 보고 와 주세요: ' + APP + '\n\n' +
    '[개인정보 안내] 수집 항목: 앱에서 쓴 닉네임, 설문 응답 / 이용 목적: 2026 제주 관광 데이터 활용사례 공모전 출품 서비스 검증·개선 / ' +
    '보유 기간: 2026년 12월 31일까지 보관 후 파기 / 이름·이메일은 받지 않아요. 응답하지 않아도 불이익은 없어요. ' +
    '경품 응모용 연락처는 마지막에 따로 동의를 받아요. (운영: 돌담랩 팀)'
  );
  form.setCollectEmail(false);
  form.setAllowResponseEdits(false);
  form.setShowLinkToRespondAgain(false);
  form.setProgressBar(true);
  form.setConfirmationMessage('응답이 저장됐어요. 도와주셔서 정말 고마워요!');

  var nickItem = form.addTextItem()
    .setTitle('앱에서 쓴 닉네임')
    .setHelpText('앱 시작 화면에서 정한 닉네임이에요. 앱에서 설문 버튼으로 들어오면 자동으로 채워져 있어요.')
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('연령대')
    .setChoiceValues(['10대', '20대', '30대', '40대', '50대 이상'])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('최근 2년 안에 제주 여행을 간 적이 있나요?')
    .setChoiceValues(['없어요', '1번', '2번 이상'])
    .setRequired(true);

  var agree = ['전혀 아니다', '매우 그렇다'];
  form.addScaleItem()
    .setTitle('앱이 쓰기 쉬웠다')
    .setBounds(1, 5).setLabels(agree[0], agree[1]).setRequired(true);
  form.addScaleItem()
    .setTitle('추천 코스대로 다녀도 비행기 시간에 맞출 수 있을 것 같다')
    .setBounds(1, 5).setLabels(agree[0], agree[1]).setRequired(true);
  form.addScaleItem()
    .setTitle('몰랐던 제주 장소를 새로 알게 됐다')
    .setBounds(1, 5).setLabels(agree[0], agree[1]).setRequired(true);
  form.addScaleItem()
    .setTitle('제주 여행 마지막 날에 실제로 쓸 것 같다')
    .setBounds(1, 5).setLabels(agree[0], agree[1]).setRequired(true);
  form.addScaleItem()
    .setTitle('친구에게 추천하고 싶다')
    .setBounds(1, 5).setLabels(agree[0], agree[1]).setRequired(true);

  form.addCheckboxItem()
    .setTitle('가장 좋았던 점 (여러 개 선택 가능)')
    .setChoiceValues([
      '공항 도착 시간에 맞춘 계산',
      '관광·일·휴식 모드',
      '식사 시간 맞춤',
      '장소 바꾸기',
      '덜 알려진 장소 추천',
      '장소별 영업시간·휴무 안내',
      '진행 화면(출발하기)'
    ])
    .showOtherOption(true);

  form.addParagraphTextItem()
    .setTitle('불편했거나 이상했던 점 (선택)')
    .setHelpText('예: 시간이 이상하게 계산됐어요, 이 장소는 문 닫았어요, 버튼이 안 눌려요');

  form.addParagraphTextItem()
    .setTitle('있으면 좋겠는 기능 (선택)');

  // ── 기프티콘 추첨 응모 (선택) ──
  var raffle = form.addPageBreakItem()
    .setTitle('기프티콘 추첨 응모 (선택)')
    .setHelpText(
      PRIZE + ' 추첨(' + WINNERS + '명, ' + DRAW_DATE + ' 발송)에 응모하려면 연락처가 필요해요.\n\n' +
      '[개인정보 수집·이용 동의 - 경품 발송]\n' +
      '수집 항목: 전화번호 또는 카카오톡 ID\n' +
      '이용 목적: 추첨 당첨자에게 기프티콘 발송\n' +
      '보유 기간: 경품 발송이 끝나면 즉시 파기\n' +
      '동의하지 않아도 설문 참여에는 영향이 없고, 추첨에서만 제외돼요.'
    );
  var contactPage = form.addPageBreakItem()
    .setTitle('연락처 입력')
    .setHelpText('당첨되면 이 연락처로 기프티콘을 보내 드려요. 한 사람당 한 번만 응모해 주세요.');
  var codeItem = form.addTextItem()
    .setTitle('응모 코드')
    .setHelpText('앱 결과 화면 맨 아래에서 별점을 보내면 나오는 LC-로 시작하는 코드예요. 앱을 실제로 써 본 분만 추첨에 들어가요.')
    .setRequired(true);
  codeItem.setValidation(
    FormApp.createTextValidation()
      .requireTextMatchesPattern('^[Ll][Cc]-[0-9A-Fa-f]{6}$')
      .setHelpText('LC-로 시작하는 9자리 코드를 그대로 적어 주세요. 예: LC-3F2B8C')
      .build()
  );
  form.addTextItem()
    .setTitle('전화번호 또는 카카오톡 ID')
    .setHelpText('예: 010-1234-5678 또는 카톡 ID')
    .setRequired(true);

  // 동의 문항은 '응모' 페이지 안에 두고, 고른 답에 따라 연락처 페이지로 가거나 바로 제출
  var consent = form.addMultipleChoiceItem()
    .setTitle('연락처 수집·이용에 동의하고 추첨에 응모할까요?')
    .setRequired(true);
  consent.setChoices([
    consent.createChoice('동의하고 응모할게요', contactPage),
    consent.createChoice('응모 안 할게요', FormApp.PageNavigationType.SUBMIT)
  ]);
  form.moveItem(consent.getIndex(), raffle.getIndex() + 1);

  var sheet = SpreadsheetApp.create('제주 라스트콜 베타 설문 응답');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, sheet.getId());

  try { form.setPublished(true); } catch (e) { /* 예전 방식 설문지는 만들면 바로 게시됨 */ }

  // 앱의 '1분 설문하고 응모하기' 버튼용: 닉네임·코드가 미리 채워지는 링크
  var prefill = form.createResponse()
    .withItemResponse(nickItem.createResponse('{nickname}'))
    .withItemResponse(codeItem.createResponse('{code}'))
    .toPrefilledUrl();

  Logger.log('친구들에게 보낼 주소: ' + form.getPublishedUrl());
  Logger.log('앱에 넣을 주소(VITE_SURVEY_URL): ' + prefill);
  Logger.log('수정 화면: ' + form.getEditUrl());
  Logger.log('응답 시트: ' + sheet.getUrl());
}
