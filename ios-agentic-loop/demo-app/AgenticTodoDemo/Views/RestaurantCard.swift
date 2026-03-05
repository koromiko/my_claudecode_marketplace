import SwiftUI

struct RestaurantCard: View {
    let restaurant: Restaurant

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(restaurant.name)
                .font(.subheadline.bold())
                .lineLimit(2)
                .accessibilityIdentifier("explore_label_name")

            HStack(spacing: 4) {
                Image(systemName: "star.fill")
                    .font(.caption)
                    .foregroundStyle(.orange)
                Text(String(format: "%.1f", restaurant.rating))
                    .font(.caption.bold())
                    .accessibilityIdentifier("explore_label_rating")
            }

            Text(restaurant.category)
                .font(.caption2.bold())
                .padding(.horizontal, 8)
                .padding(.vertical, 2)
                .background(Color.orange.opacity(0.15))
                .foregroundStyle(.orange)
                .clipShape(Capsule())
                .accessibilityIdentifier("explore_label_category")
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Color(.systemGray6))
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .accessibilityIdentifier("explore_card_\(restaurant.id.uuidString.prefix(8))")
    }
}
