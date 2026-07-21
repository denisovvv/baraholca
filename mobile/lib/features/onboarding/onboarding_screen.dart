import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../../core/theme/app_colors.dart';

/// Данные одного слайда онбординга.
class _OnboardingSlide {
  const _OnboardingSlide({
    required this.title,
    required this.svgIcon,
    this.description,
    this.showLogo = false,
  });

  final String title;
  final String svgIcon;
  final String? description; // подзаголовок (у слайда 1 его нет)
  final bool showLogo;
}

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final PageController _pageController = PageController();
  int _currentPage = 0;

  static const List<_OnboardingSlide> _slides = [
    _OnboardingSlide(
      title: 'Товары от проверенных продавцов — в одном приложении',
      svgIcon: 'assets/icons/onboarding_shop.svg',
      showLogo: true,
    ),
    _OnboardingSlide(
      title: 'Со склада и под заказ',
      description: 'Тысячи товаров в наличии и изделия под заказ, включая 3D-печать',
      svgIcon: 'assets/icons/onboarding_box.svg',
    ),
    _OnboardingSlide(
      title: 'Доставим или заберёте сами',
      description: 'Курьер по вашему адресу или самовывоз с пункта — как удобно',
      svgIcon: 'assets/icons/onboarding_truck.svg',
    ),
    _OnboardingSlide(
      title: 'Реальные отзывы и оценки',
      description: 'Покупайте уверенно — по честным отзывам других покупателей',
      svgIcon: 'assets/icons/onboarding_star.svg',
    ),
  ];

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  bool get _isLastPage => _currentPage == _slides.length - 1;

  void _onNext() {
    if (_isLastPage) {
      return;
    }
    _pageController.nextPage(
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeInOut,
    );
  }

  void _onSkip() {}

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: Stack(
        children: [
          Positioned(
            top: 120,
            left: 0,
            right: 0,
            child: Center(
              child: Container(
                width: 380,
                height: 380,
                decoration: const BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [Color(0x1AFFD500), Color(0x00FFD500)],
                    stops: [0.0, 0.7],
                  ),
                ),
              ),
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24),
              child: Column(
                children: [
                  SizedBox(
                    height: 44,
                    child: Align(
                      alignment: Alignment.centerRight,
                      child: GestureDetector(
                        onTap: _onSkip,
                        child: const Text(
                          'Пропустить',
                          style: TextStyle(
                            color: AppColors.textSecondary,
                            fontSize: 15,
                          ),
                        ),
                      ),
                    ),
                  ),
                  Expanded(
                    child: PageView.builder(
                      controller: _pageController,
                      itemCount: _slides.length,
                      onPageChanged: (index) {
                        setState(() => _currentPage = index);
                      },
                      itemBuilder: (context, index) {
                        return _SlideView(slide: _slides[index]);
                      },
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.only(top: 24, bottom: 20),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: List.generate(
                        _slides.length,
                        (index) => _Dot(isActive: index == _currentPage),
                      ),
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.only(bottom: 34),
                    child: SizedBox(
                      width: double.infinity,
                      height: 56,
                      child: ElevatedButton(
                        onPressed: _onNext,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.primary,
                          foregroundColor: AppColors.background,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(14),
                          ),
                          textStyle: const TextStyle(
                            fontSize: 17,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        child: Text(_isLastPage ? 'Начать' : 'Далее'),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SlideView extends StatelessWidget {
  const _SlideView({required this.slide});

  final _OnboardingSlide slide;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Container(
          width: 160,
          height: 160,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: AppColors.card,
            border: Border.all(color: const Color(0xFF333336), width: 1.5),
          ),
          child: Center(
            child: SvgPicture.asset(slide.svgIcon, width: 72, height: 72),
          ),
        ),
        const SizedBox(height: 28),
        if (slide.showLogo) ...[
          Image.asset('assets/logo-no-sub.png', width: 180),
          const SizedBox(height: 28),
        ],
        Text(
          slide.title,
          textAlign: TextAlign.center,
          style: const TextStyle(
            fontSize: 28,
            fontWeight: FontWeight.w800,
            color: AppColors.textPrimary,
            height: 1.2,
            letterSpacing: -0.4,
          ),
        ),
        // Описание (подзаголовок) — если есть.
        if (slide.description != null) ...[
          const SizedBox(height: 12),
          Text(
            slide.description!,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 15,
              color: AppColors.textSecondary,
              height: 1.4,
            ),
          ),
        ],
      ],
    );
  }
}

class _Dot extends StatelessWidget {
  const _Dot({required this.isActive});

  final bool isActive;

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      margin: const EdgeInsets.symmetric(horizontal: 3.5),
      width: isActive ? 20 : 7,
      height: 7,
      decoration: BoxDecoration(
        color: isActive ? AppColors.primary : const Color(0xFF3A3A3E),
        borderRadius: BorderRadius.circular(4),
      ),
    );
  }
}
